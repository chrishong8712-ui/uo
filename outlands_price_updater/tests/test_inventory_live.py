import threading
import unittest

from core.inventory_ocr import (
    InventoryAccumulator,
    green_text_mask,
    item_name,
    razor_messages,
    watch_region,
)


OCR_FRAME = (
    "00:36 |||[Razon]? Added 1152616016 to ignore list\n"
    "00:36 ||[Razon]? provocation skill mastery scroll\n"
    "[used to increase a player's skill cap\n"
    "for a skill by 1)\n"
    "00:36 ||[Razon]? Added 1152617474 to ignore\n"
    "list\n"
    "00:36 || [Razor]? mining skill mastery scroll\n"
    "[used to increase a player's skill cap\n"
    "for a skill by 1)\n"
    "00:36 || [Razor]? Ignore List cleared\n"
    "00:36 |||[Razor]? Label dump done."
)


class RazorMessageParsingTests(unittest.TestCase):
    def test_joins_wrapped_lines_into_one_message(self):
        bodies = razor_messages(OCR_FRAME)
        self.assertIn(
            "mining skill mastery scroll [used to increase a player's skill cap for a skill by 1)",
            bodies,
        )

    def test_ignores_non_razor_system_messages(self):
        text = "00:35 || You have been healed.\nsome stray line\n" + OCR_FRAME
        self.assertFalse(any("healed" in body for body in razor_messages(text)))
        self.assertFalse(any("stray" in body for body in razor_messages(text)))

    def test_item_name_cuts_description_and_drops_script_output(self):
        self.assertEqual(
            item_name("mining skill mastery scroll [used to increase a player's skill cap"),
            "mining skill mastery scroll",
        )
        self.assertEqual(
            item_name("provocation skill mastery scroll (used to increase"),
            "provocation skill mastery scroll",
        )
        self.assertIsNone(item_name("Added 1152616016 to ignore list"))
        self.assertIsNone(item_name("Ignore List cleared"))
        self.assertIsNone(item_name("Label dump done."))

    def test_real_run_noise_is_dropped_and_misreads_are_cut(self):
        text = (
            "00:40 || [Razor]? Select target for variable 'sean container'\n"
            "00:40 || [Razor]? script variable updated\n"
            "layers\n"
            "Recents\n"
            "00:41 || [Razor]? armslore seroll\n"
            "[used to inerease a player's skill cap\n"
            "for a skill by 1)\n"
            "fa) iqnore\n"
            "00:42 || [Razor]? musicanship skill mastery scroll\n"
            "[used to increase a playeris skill cap\n"
            "for a skill by 1)\n"
        )
        bodies = razor_messages(text)
        names = [name for name in (item_name(body) for body in bodies) if name]
        self.assertEqual(
            names,
            ["armslore seroll", "musicanship skill mastery scroll"],
        )
        self.assertFalse(any("layers" in body or "Recents" in body for body in bodies))
        self.assertFalse(any("iqnore" in body for body in bodies))

    def test_item_name_strips_ocr_noise_prefix(self):
        self.assertEqual(
            item_name("1 skilll mastery scroll (used"),
            "skilll mastery scroll",
        )


class GreenTextMaskTests(unittest.TestCase):
    def _pixel_image(self, color):
        from PIL import Image

        return Image.new("RGB", (4, 4), color)

    def test_green_text_becomes_black(self):
        mask = green_text_mask(self._pixel_image((24, 238, 0)))
        self.assertEqual(mask.getpixel((0, 0)), 0)

    def test_yellow_system_text_is_removed(self):
        mask = green_text_mask(self._pixel_image((238, 238, 0)))
        self.assertEqual(mask.getpixel((0, 0)), 255)

    def test_grey_and_white_are_removed(self):
        self.assertEqual(green_text_mask(self._pixel_image((200, 200, 200))).getpixel((0, 0)), 255)
        self.assertEqual(green_text_mask(self._pixel_image((255, 255, 255))).getpixel((0, 0)), 255)


class RazorTagTests(unittest.TestCase):
    def test_label_dump_control_messages_are_dropped(self):
        text = (
            "00:47 | [Rezer]: Added 1152623066\n"
            "te ignere list\n"
            "00:47 | [Razer]: Iqnere List cleared\n"
            "00:47 | [Razer]: Label dump done.\n"
        )
        self.assertEqual(
            [m for m in razor_messages(text) if item_name(m)],
            [],
        )

    def test_misread_razor_tag_variants_are_accepted(self):
        text = (
            "00:50 || Razer: mining skill mastery scroll\n"
            "00:51 || [Razon]? armslore scroll\n"
            "00:52 || [Razor]: tracking scroll\n"
        )
        self.assertEqual(len(razor_messages(text)), 3)


class InventoryAccumulatorTests(unittest.TestCase):
    def test_extracts_item_names_once_across_frames(self):
        accumulator = InventoryAccumulator()
        self.assertEqual(
            accumulator.add_text(OCR_FRAME),
            ["provocation skill mastery scroll", "mining skill mastery scroll"],
        )
        self.assertEqual(accumulator.add_text(OCR_FRAME), [])
        self.assertEqual(
            accumulator.text(),
            "provocation skill mastery scroll\nmining skill mastery scroll",
        )

    def test_reports_finished_on_label_dump_done(self):
        accumulator = InventoryAccumulator()
        accumulator.add_text("00:10 || Something else")
        self.assertFalse(accumulator.finished)
        accumulator.add_text(OCR_FRAME)
        self.assertTrue(accumulator.finished)

    def test_match_maps_item_names_to_variables(self):
        accumulator = InventoryAccumulator()
        accumulator.add_text(
            "00:36 || [Razor]: Plainly drawn [used to increase]\n"
            "00:36 || [Razor]: Dull copper [used to increase]"
        )
        match = accumulator.match()
        self.assertIn("T1Price", match.owned)
        self.assertIn("DullCopperOreMapPrice", match.owned)


class WatchRegionTests(unittest.TestCase):
    def test_captures_repeatedly_and_reports_new_lines(self):
        frames = [
            "00:36 || [Razor]: Plainly drawn [used",
            "00:36 || [Razor]: Plainly drawn [used\n00:36 || [Razor]: Dull copper [used",
            "00:36 || [Razor]: Dull copper [used",
        ]
        region = (10, 20, 300, 100)
        captured_regions = []
        stop_event = threading.Event()
        reported = []

        def fake_capture(bbox):
            captured_regions.append(bbox)
            return len(captured_regions)

        def fake_engine(frame_index):
            return frames[frame_index - 1]

        def on_new_lines(lines):
            reported.append(lines)
            if len(reported) == 2:
                stop_event.set()

        accumulator = InventoryAccumulator()
        captures = watch_region(
            region,
            accumulator,
            stop_event,
            on_new_lines=on_new_lines,
            interval_s=0,
            capture=fake_capture,
            engine=fake_engine,
        )

        self.assertEqual(captures, 2)
        self.assertEqual(captured_regions, [region, region])
        self.assertEqual(reported, [["Plainly drawn"], ["Dull copper"]])
        self.assertEqual(accumulator.text(), "Plainly drawn\nDull copper")

    def test_stops_capturing_once_done_message_is_read(self):
        frames = iter([
            "00:36 || [Razor]: Air [used",
            "00:37 || [Razor]: Label dump done.",
        ])
        calls = []

        def fake_capture(bbox):
            calls.append(bbox)
            return None

        accumulator = InventoryAccumulator()
        captures = watch_region(
            (0, 0, 1, 1),
            accumulator,
            threading.Event(),
            interval_s=0,
            capture=fake_capture,
            engine=lambda image: next(frames),
        )
        self.assertEqual(captures, 2)
        self.assertTrue(accumulator.finished)

    def test_does_not_capture_when_stop_already_set(self):
        stop_event = threading.Event()
        stop_event.set()
        calls = []
        captures = watch_region(
            (0, 0, 1, 1),
            InventoryAccumulator(),
            stop_event,
            interval_s=0,
            capture=lambda bbox: calls.append(bbox),
            engine=lambda image: "",
        )
        self.assertEqual(captures, 0)
        self.assertEqual(calls, [])

    def test_repeated_identical_frames_report_nothing_new(self):
        stop_event = threading.Event()
        reported = []
        counter = {"n": 0}

        def fake_capture(bbox):
            counter["n"] += 1
            if counter["n"] == 3:
                stop_event.set()
            return None

        watch_region(
            (0, 0, 1, 1),
            InventoryAccumulator(),
            stop_event,
            on_new_lines=reported.append,
            interval_s=0,
            capture=fake_capture,
            engine=lambda image: "00:36 || [Razor]: Air [used",
        )
        self.assertEqual(reported, [["Air"]])


if __name__ == "__main__":
    unittest.main()

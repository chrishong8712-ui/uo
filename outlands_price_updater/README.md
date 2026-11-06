# Outlands Razor price updater

이 도구는 사용자가 직접 로그인한 Outlands Portal 브라우저 세션에서 Vendor Search를 순차적으로 조회하고, 조회한 가격으로 Razor 스크립트 전체를 코드(`core\razor_generator.py`)에서 생성합니다. 참고용 Razor 파일을 읽지 않으므로 해당 파일이 없어도 실행됩니다.

## 폴더 구성

- `price_updater.py`: 실행 진입점(`core.cli.main` 호출)
- `core\`: UI와 분리된 핵심 코드
  - `cli.py`: 콘솔 입출력과 인자 처리
  - `workflow.py`: 갱신 전체 흐름(`run_update`), 보유 아이템 계획(`plan_owned_search`)
  - `collector.py`: 순차 조회 오케스트레이션, 콜백(`CollectHooks`)으로 입출력 주입
  - `site_search.py`: Vendor Search 브라우저 조작, 차단/챌린지 감지
  - `checkpoint.py`: 진행 파일 저장/불러오기
  - `price_logic.py`, `inventory_ocr.py`, `rare_cloth.py`, `rare_items.py`, `razor_generator.py`, `search_catalog.py`: 가격 계산, OCR, rare item 정의, Razor 생성
- `tests\`: 단위 테스트
- `razor\`: 게임에서 쓰는 참고/출력용 Razor 파일(`owned_label_dump.razor`, `vendor.razor`, `Item names and serials.razor`)


## 실행

Python 3.10 이상을 설치한 다음 PowerShell에서 한 번 설정합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m playwright install chromium
```

```powershell
py price_updater.py
```

브라우저가 열리면 사용자가 직접 로그인하고, 터미널로 돌아와 Enter를 누릅니다. 조회를 시작하려면 다음 확인 단계에서 `START`를 입력해야 합니다. 비밀번호를 도구에 입력하거나 전달하지 않습니다. 로그인 세션은 `%LOCALAPPDATA%\OutlandsPriceUpdater\browser-profile`의 전용 Chromium 프로필에 남아 다음 실행에서도 재사용할 수 있습니다. 로그아웃하려면 브라우저에서 직접 로그아웃하거나 프로그램을 닫은 뒤 해당 프로필 폴더를 직접 제거하세요.

출력 기본 경로는 실행한 폴더의 `price_script.razor`입니다. 기존 출력 파일은 덮어쓰지 않습니다. 다른 경로를 지정할 수 있습니다.

```powershell
py price_updater.py --output "C:\경로\priced.razor"
```

## 보유 아이템 OCR (선택 사항)

게임 안에서 UO Razor 스크립트가 보유 아이템 목록을 system message로 출력하는 동안, 그 영역을 Tesseract로 읽어 보유 아이템의 가격만 조회할 수 있습니다.

- 출력 스크립트: `razor\owned_label_dump.razor`는 `razor\vendor.razor`의 검증된 명령만 사용해 아이템 label을 `sysmsg`로 출력하며, 아이템을 옮기지 않습니다(`lift`/`drop` 미사용). 대상 컨테이너를 프롬프트에서 지정합니다.
- 게임 실행 확인: 사용자가 게임에서 이 스크립트가 정상 실행되는 것을 확인했습니다. 중복 출력은 OCR 단계에서 제거됩니다.
- OCR 영역: 게임창 기준 고정 좌표 `(0, 300, 410, 720)` (x,y,너비,높이 = 왼쪽 위 0,300 / 오른쪽 아래 410,1020)을 코드(`INVENTORY_REGION`)에 설정해 두었습니다. 다른 창 배치라면 `--inventory-region x,y,w,h`로 덮어씁니다.
- 글자 크기: 게임 내 글자 크기 25 기준으로 맞춰져 있습니다. 글자 크기를 바꾸면 스크롤 속도가 달라지므로 `owned_label_dump.razor`의 `wait` 값을 늘려 조정하세요.

1. Tesseract 설치: Windows용 [UB-Mannheim 빌드](https://github.com/UB-Mannheim/tesseract/wiki)를 설치합니다. 기본 경로(`C:\Program Files\Tesseract-OCR\tesseract.exe`)에 있으면 자동으로 찾고, 다른 위치라면 환경 변수 `TESSERACT_CMD`에 실행 파일 경로를 지정합니다.
2. Python 패키지 설치: `py -m pip install -r requirements.txt` (pytesseract, Pillow 포함)
3. 실행 방법: 옵션 없이 `py price_updater.py`를 실행하면 모드를 묻습니다(1: 전체 가격 검색, 2: 보유 아이템만 실시간 OCR). 묻지 않고 바로 실행하려면 아래 옵션을 씁니다.
   - 전체 검색: `py price_updater.py --all`
   - 이미지 파일: `py price_updater.py --inventory-image "C:\경로\inventory.png"`
   - 실시간 화면 OCR: `py price_updater.py --inventory-live` (고정 영역 사용, 다른 영역이면 `--inventory-region x,y,w,h`)
     - 실행하면 고정 영역을 0.4초 간격으로 반복 캡처·OCR합니다(사이트 요청 없음).
     - 그 사이 게임에서 owned_label_dump.razor를 실행해 system message가 영역 안에 보이도록 합니다. 새로 읽힌 아이템은 `+`로 표시됩니다.
     - 시작 전에 영역 안의 오래된 메시지를 지우거나 그대로 두어도 됩니다(이미 보이는 메시지도 읽힘). 게임 로그는 비우지 않아도 됩니다.
     - 필터: 녹색 글씨 `[Razor]` 메시지만 아이템으로 사용합니다. 노란색 등 다른 색의 시스템 메시지는 무시합니다. 설명(`[used to increase...`)은 이름에서 잘라내며, `added`/`ignore list` 같은 스크립트 상태 줄은 아이템 이름이 아니므로 무시합니다.
     - OCR은 영역을 3배 확대한 뒤 읽습니다. 글자 사이 공백은 무시하고 매칭합니다(예: `lumber jacking` → Lumberjacking).
     - 스크립트가 끝나도(`Label dump done`) 도구는 자동으로 멈추지 않습니다. 모든 메시지를 읽었으면 터미널에서 Enter를 눌러 중지하고, 그때까지 읽은 줄로 판단합니다.
     - 좌표는 화면 픽셀 기준이며 Windows 배율(DPI)에 따라 달라집니다. 배율이 100%가 아니면 캡처 결과를 한 번 확인하세요.
   - Rare cloth: OCR 줄이 `rare cloth (hue 번호: 이름)` 형식이면 **hue 번호**로 종류를 판별합니다(`rare cloth (hue N:`). 보유한 종류만 동적으로 `RareCloth{N}Price` 변수와 Razor 섹션이 추가되며, 확인 목록에 hue와 OCR 줄이 표시됩니다. hue 숫자를 읽을 수 없으면(예: `2O85`) 추측하지 않고 "매핑되지 않음"으로 보고합니다. `(used ...)` 설명은 버립니다. 전체 검색 모드(1/`--all`)에는 rare cloth가 포함되지 않습니다.
4. 도구는 OCR 텍스트, 보유로 판단한 아이템, 매핑되지 않은 줄, 여러 변수에 걸친 모호한 줄을 출력하고 `YES`를 입력해야 진행합니다.

- 보유 아이템으로 확인된 변수만 조회합니다. 조회하지 않은 변수는 스크립트에 `'0'`으로 기록되며, 요약에 "보유 아님(0)" 목록으로 표시됩니다.
- 매핑되지 않았거나 모호한 줄은 기본값으로 처리하지 않고 목록으로만 표시합니다.
- OCR은 아이템 이름(label)만 매칭합니다. 게임 메시지가 ID만 출력하면 매칭되지 않으므로 목록에 표시됩니다.
- 가격 `0`은 벤더에 0으로 올렸을 때 미판매로 분류되는 것을 사용자가 확인했습니다(게임 내 동작은 사용자 확인 기준이며, 생성 Razor 블록 자체는 0을 별도로 건너뛰지 않습니다).

테스트는 다음 명령으로 실행합니다.

```powershell
py -m unittest discover -s tests -t .
```

## 실패 시 재시도 및 이어서 실행

- 항목의 가격을 읽지 못하면(검색 결과 없음, 로딩 시간 초과, 가격 파싱 실패 등) 중단하지 않고 해당 항목에서 멈춰 물어봅니다. Enter를 누르면 Vendor Search 페이지를 다시 열고 같은 항목을 다시 조회하며, `Q`를 입력하면 중단합니다. 자동 재시도는 하지 않습니다.
- 429/403/CAPTCHA 같은 접근 제한은 재시도 없이 즉시 중단합니다.
- 항목 하나를 성공할 때마다 `<출력파일>.progress.json`에 진행 상황이 저장됩니다. 중단된 뒤 다시 로그인하고 `py price_updater.py --resume`(같은 `--output` 사용)으로 실행하면 이미 읽은 항목은 건너뜁니다. 이전 가격은 그대로 쓰이므로 진행 파일은 **처음 만들어진 시점부터 7일 이내**일 때만 사용됩니다(저장할 때마다 갱신되지 않음). 7일이 지났거나 생성 시각이 없는 진행 파일은 가격을 사용하지 않고 오류로 알리므로, 삭제한 뒤 처음부터 다시 시작하세요. 진행 파일이 있는데 `--resume`이 없으면 실행하지 않으며, 모든 항목이 끝나 스크립트가 생성되면 진행 파일은 삭제됩니다.

## 가격 산정 및 보호 동작

- Vendor Search의 자동완성 항목을 UI에서 선택한 뒤 결과의 `Price` 오름차순을 확인하고, 맨 위 매물부터 숫자 단가 10개까지 산정에 사용합니다. `warning`으로 시작하는 모든 가격 셀(고정값/범위 표시 모두)은 무시하고 다음 매물에서 숫자 단가를 확인합니다. 최저가 하나를 그대로 택하지 않고 이 표본의 `Listed`에서 2개월 이상 지난 매물을 제외합니다. 최신 매물이 5개 이하이면 가장 최근 매물 가격을 사용합니다. 6개 이상이면 가격 중앙값을 구하고, 최저·최고가 차이가 2배 이상일 때 중앙값의 절반 미만 또는 2배 초과 가격을 제외한 나머지의 평균을 사용합니다. 그 외에는 모든 최근 매물 가격의 평균을 사용하며 소수점은 버립니다. `Total` 열은 사용하지 않습니다.
- 항목별로 한 번에 하나씩 조회합니다. 검색어 입력 후 자동완성 목록을 확인하기 전 2초, 검색 사이에 고정 2초를 기다리며, 각 항목 로그에 실제 검색/결과 로딩 시간도 표시합니다. CAPTCHA/접근 챌린지, HTTP 401/403/429/서버 오류, 항목 불일치, 가격 파싱 실패 또는 검색 결과 없음이 발생하면 즉시 중단합니다. 모든 변수를 성공적으로 읽기 전에는 결과 파일을 만들지 않습니다.
- Portal은 새 매물이 Vendor Search에 나타나기까지 15분 지연된다고 안내합니다. 이 도구는 사이트의 표시된 결과만 읽으며 더 최신 매물이나 가격을 보장하지 않습니다.
- Aspect core/distillation은 `{aspect} aspect core` / `{aspect} aspect distillation` 이름으로 Vendor Search에서 조회합니다. Chromatic 검색어는 `chromatic core` / `chromatic distillation`입니다. 생성하는 Razor의 `findtype`은 `razor\Item names and serials.razor`에 기재된 실제 type alias인 `chroma core` / `chroma distil`을 사용합니다. Phylactery는 Chromatic을 제외한 각 aspect의 `{aspect} phylactery`로 조회하며, Razor에서는 `phylacteryContainer`의 랜덤 좌표에 배치합니다(25개). 좌표는 vendor로 옮기는 처리 단계에서만 사용합니다.

**Razor 컨테이너 좌표 규칙**: 모든 컨테이너(맵, 자원 맵, core, distillation, phylactery, skill scroll, rare item, rare cloth)의 좌표는 `LAYOUT_SEED = 20240601` 고정 시드로 생성한 난수입니다(`core\razor_generator.py`의 `_randomized`, `rare_cloth_section`). x, y는 모두 0–60 정수이며, 같은 컨테이너 안의 두 아이템은 Chebyshev 거리 `max(|dx|, |dy|)`가 5 이상입니다. 아이템끼리의 겹침은 허용합니다. 시드를 바꾸면 전체 좌표가 바뀝니다. 섹션 표의 x/y 값은 설계용 자리표시자이며 실제 좌표로 쓰이지 않습니다. 게임 내 배치는 아직 검증하지 않았습니다.
- Rare cloth(type `folded cloth`)는 고정 목록 없이 OCR로 확인한 보유 종류만 hue 번호로 동적 처리합니다. 검색은 `rare cloth {hue}`, 자동완성에서 `rare cloth (hue {hue}:`로 시작하는 항목만 선택합니다(사이트에서 확인됨). 변수명은 `RareCloth{hue}Price`이며, Razor에서는 `findtype 'folded cloth'` 후 label에 `hue {hue}`가 포함되는지로 구분하고 `rareClothContainer`의 좌표는 아래 랜덤 레이아웃 규칙으로 배치합니다. 게임 내 label 형식과 `findtype`의 hue 필터, 컨테이너 y 범위는 아직 게임에서 검증하지 않았습니다.
- Ore, lumber, fishing, skinning resource map은 사이트 자동완성에서 확인한 정식 명칭 36개(각 계열 9개)로 조회하고, 각각의 가격 변수와 전용 Razor 처리 루프를 생성합니다. 예를 들어 Ore Map은 `dull copper ore map`, `shadow iron ore map`, `agapite ore map` 등 실제 자동완성 이름을 사용합니다. Razor `findtype`은 참고 파일의 별칭 `ore map`, `lumber map`, `fishing map`, `skinning map`을 사용하며, 일반 treasure map의 `map` 타입과 구분합니다. Resource Maps용 컨테이너는 스크립트 실행 중 지정합니다.
- `copper ore map` 자동완성은 `copper` 부분 문자열로 선택하지 않고 항목 제목 전체를 정확히 비교하므로 `dull copper ore map`과 구분됩니다.
- 일반 Treasure Map은 Vendor Search 자동완성에서 확인한 7종(`plainly`/`expertly`/`adeptly`/`cleverly`/`deviously`/`ingeniously`/`legendarily drawn treasure map`, 레벨 1–6 및 8)만 조회합니다. 레벨 7은 자동완성 결과가 없어 제외하며, `ancient abyssal treasure map`은 검색 및 Razor 처리 대상에서 제외합니다. Razor `findtype 'map'`으로 처리하고 Resource Map과 별도 컨테이너를 사용합니다.
- Chromatic core/distillation(`chroma core` / `chroma distil`)은 항상 스크립트에 포함됩니다.
- Skill Mastery Scroll은 scroll 계열입니다. 검색어는 `{skill} skill mastery scroll`, Razor type/loop 이름은 `scroll of calling`입니다.
- Skill Mastery Orb는 scroll과 분리된 rare item입니다(`core\rare_items.py`). 검색어는 `skill mastery orb`, Razor type은 `void orb`입니다. 같은 방식으로 `mastercrafting diagram`(Razor type `Book of Truth`), `research materials`(Razor type `research materials`)도 rare item으로 등록되어 있습니다. 세 항목의 검색어는 사이트 자동완성에서 정식 이름과 일치함을 확인했습니다(`mastercrafting diagram` 90건, `research materials`). 검색어와 type은 별도 필드로 관리합니다. 생성 스크립트의 `Rare Items` 섹션(`rareItemsContainer`)에 `SkillOrbPrice`, `MastercraftingDiagramPrice`, `ResearchMaterialsPrice`가 포함되며, 배치 좌표는 위의 랜덤 레이아웃 규칙을 따릅니다.
- Arcane Scroll은 rare item입니다(`core\rare_items.py`). 검색어와 자동완성 정식 항목명은 `an arcane scroll`, Razor type(`findtype`)은 `blank scroll%s%`입니다. 검색어와 type은 별도 필드로 관리하며, 스크립트의 `Rare Items` 섹션에 `ArcaneScrollPrice`로 포함됩니다.
- 생성되는 스크립트는 선언, 컨테이너 처리, 루프 순서를 코드에 정의한 레이아웃대로 만듭니다. 가격을 확인하지 못한 변수나 누락/잘못된 값이 있으면 기본값으로 바꾸지 않고 파일을 만들지 않습니다.

기본 매핑이 실제 항목과 다르면 `search_overrides.example.json`을 복사해 `search_overrides.json`으로 저장하고 변수별 `search`(검색어)와 `match`(자동완성 제목에 포함되어야 할 문구)를 편집하세요. 프로그램은 해당 파일이 작업 폴더에 있을 때 자동으로 사용합니다. 예를 들어:

```json
{
  "DullCopperOreMapPrice": {
    "search": "dull copper ore map",
    "match": "dull copper ore map"
  }
}
```

## Windows 실행 파일 빌드

같은 가상 환경에서 다음 명령으로 폴더형 실행 파일을 빌드할 수 있습니다.

```powershell
py -m pip install pyinstaller
py -m PyInstaller --onedir --console --name OutlandsPriceUpdater --collect-all playwright price_updater.py
```

실행 파일은 `dist\OutlandsPriceUpdater\OutlandsPriceUpdater.exe`에 생성됩니다. Chromium도 실행할 컴퓨터에서 설치해야 합니다(`py -m playwright install chromium`). 예제 Razor 스크립트는 저작권이 있는 사용자 제공 콘텐츠이므로 프로젝트에 복사해 포함하지 않습니다.

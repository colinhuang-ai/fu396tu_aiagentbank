# Bộ công cụ xử lý tài liệu

`tools/` chứa các công cụ nội bộ, mỗi công cụ là một package độc lập và tự chứa:

| Công cụ | Việc | Lối tắt |
|---|---|---|
| [`tools/anonymize`](tools/anonymize) | mã hóa / giải mã email, SĐT, tên người trong tài liệu | `python anonymize.py` |
| [`tools/organize`](tools/organize) | đổi tên hàng loạt và sắp xếp tài liệu vào thư mục | `python organize.py` |

Cả hai đều có skill tương ứng trong `.agents/skills/` để agent gọi được từ thư mục bất kỳ.

---

# anonymize — Mã hóa / giải mã thông tin nhạy cảm

Mã hóa email, số điện thoại và tên người trong file dữ liệu, **giữ nguyên cấu trúc file**
và **cho phép giải mã ngược lại** khi cần trích xuất. Có cả **giao diện web kéo-thả** lẫn **CLI**,
dùng chung một lõi xử lý.

```
loretoa@isb.ac.th   ->   enc1eiyclj7gfikdtquu6fc7gdg5jw55tocciu2rjy@isb.ac.th
+84 912 345 678     ->   enc1p3m2qsioyphzd2d4d26xvlktxaoy4zn6u7vyzlh5v7dsn4mskqi
Nguyen Van An:      ->   enc1nndgiwyvvf6l2uzftlxcne4tiqdtfaqz53zduqyx7lgvl5eq:
```

Domain (`@isb.ac.th`) được giữ nguyên để bạn vẫn thống kê được theo tổ chức;
chỉ phần định danh cá nhân bị mã hóa.

## Cấu trúc

`tools/` là nơi chứa các bộ công cụ nội bộ; mỗi công cụ là một package độc lập, tự chứa
(kể cả tài nguyên giao diện của nó), nên thêm/bớt công cụ không ảnh hưởng lẫn nhau.

```
anonymize.py                     lối tắt  ==  python -m tools.anonymize
tools/
  anonymize/
    core.py                      khóa (.env), nguyên thủy AES-SIV, lớp Cipher
    encrypt.py                   nhận diện + mã hóa email / SĐT / tên người
    decrypt.py                   tìm token + khôi phục giá trị gốc
    fileio.py                    điều phối file, đặt tên đầu ra, bảng đối chiếu
    cli.py                       dòng lệnh
    server.py                    web server (chỉ dùng stdlib)
    selftest.py                  kiểm thử nhanh
    web/index.html               giao diện kéo-thả
    handlers/                    mỗi loại file một module
      base.py                    giao ước chung + TextHandler
      plain.py                   .csv .tsv .txt .json ...
      xlsx.py                    .xlsx .xlsm
      docx.py                    .docx
      pdf.py                     .pdf  (xuất ra .txt)
      transcript.py              .vtt .srt + biên bản họp .txt
      eml.py                     .eml
.agents/skills/anonymize/
  SKILL.md                       hướng dẫn cho agent
  scripts/anonymize.py           wrapper chạy được từ thư mục bất kỳ
  references/architecture.md     kiến trúc, AES-SIV, định dạng token
  references/handlers.md         chi tiết handler + cách thêm định dạng mới
```

Chiều phụ thuộc một chiều: `cli / server → fileio → handlers/* → encrypt, decrypt → core`.
`core.py` cố tình không biết email hay số điện thoại là gì — nó chỉ giữ khóa và làm AEAD.

Dùng như thư viện:

```python
from tools.anonymize import Cipher, resolve_key, process_bytes

cipher = Cipher(resolve_key(".env"))
out = process_bytes(raw, "data.csv", cipher, "encrypt")
```

Gọi qua skill (chạy được từ thư mục bất kỳ):

```bash
python .agents/skills/anonymize/scripts/anonymize.py encrypt -i data.csv
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## 1. Tạo khóa

```bash
python anonymize.py genkey
```

Tạo file `.env` chứa `ANONYMIZE_KEY` (64 byte ngẫu nhiên, base64).

> **Quan trọng:** sao lưu `.env` ở nơi an toàn. Mất khóa = không giải mã lại được.
> File `.gitignore` đã loại `.env` khỏi git.

## 2a. Giao diện web (kéo thả file)

```bash
python anonymize.py serve
```

Trình duyệt tự mở `http://127.0.0.1:8765`. Chọn **Mã hóa** / **Giải mã**, kéo thả file
(nhiều file cùng lúc được), kết quả tải về ngay kèm bảng đối chiếu. Loại file được nhận
tự động, hoặc chọn tay ở ô **Loại file**.

Server chỉ lắng nghe trên `127.0.0.1`, không dùng thư viện ngoài — dữ liệu không rời khỏi máy.

| Cờ | Ý nghĩa |
|---|---|
| `--port 8080` | đổi cổng nếu 8765 đã bận |
| `--no-browser` | không tự mở trình duyệt |
| `--env other.env` | dùng file khóa khác |

## 2b. Mã hóa bằng dòng lệnh

```bash
python anonymize.py encrypt -i students.tsv -o students.enc.tsv --mapping map.csv
```

```bash
python anonymize.py encrypt -t "Cindy	BAO	loretoa@isb.ac.th | miokc@isb.ac.th"
```

## 3. Giải mã bằng dòng lệnh

```bash
python anonymize.py decrypt -i students.enc.tsv -o students.tsv --strict
```

## Các loại file

```bash
python anonymize.py kinds
```

| `--kind` | Loại file | Đuôi | Ghi chú |
|---|---|---|---|
| `text` | CSV / TSV / TXT / JSON … | `.csv .tsv .txt .json .xml .yaml .sql .md …` | xử lý theo nội dung nên không phá cấu trúc cột; giữ nguyên BOM và CRLF |
| `xlsx` | Excel | `.xlsx .xlsm` | quét mọi sheet, chỉ đụng ô kiểu chuỗi — ô số, ngày, công thức giữ nguyên |
| `docx` | Word | `.docx` | thân bài, bảng, text box, đầu/chân trang; gộp run nên bắt được cả email bị Word xé làm nhiều đoạn |
| `pdf` | PDF văn bản | `.pdf` | **xuất ra `.txt`** — xem ghi chú bên dưới |
| `transcript` | Biên bản / phụ đề họp | `.vtt .srt .sbv` + `.txt` tự đoán | mã hóa thêm **tên người nói**; mốc thời gian, số cue giữ nguyên |
| `email` | Thư điện tử | `.eml .mbox` | header địa chỉ, tên hiển thị, Subject và thân thư — kể cả thân mã hóa base64 / quoted-printable |

Mặc định `--kind auto`: nhận theo đuôi file, riêng `.txt` còn được đoán thêm theo nội dung
(có `WEBVTT`, thẻ `<v ...>`, hoặc nhiều dòng dạng `Tên:` → coi là transcript).
Ép tay khi cần:

```bash
python anonymize.py encrypt -i bien-ban-hop.txt --kind transcript
```

### Riêng PDF

PDF không sửa được tại chỗ mà không phá bố cục (chữ đặt theo tọa độ tuyệt đối), nên handler
**trích văn bản ra rồi mã hóa, xuất thành `.txt`**. Đây là đánh đổi có chủ ý: giữ được khả năng
giải mã chính xác, đổi lại mất bố cục trang. Chiều ngược lại giải mã từ chính file `.txt` đó.
PDF scan không có lớp văn bản → báo lỗi rõ ràng, cần OCR trước.

## Tùy chọn

| Cờ | Ý nghĩa |
|---|---|
| `--env <path>` | dùng file `.env` khác (nhiều môi trường / nhiều khóa) |
| `--kind <loại>` | ép handler thay vì tự nhận |
| `--mapping <file.csv>` | [encrypt] xuất bảng đối chiếu gốc → token |
| `--normalize-phone` | [encrypt] chuẩn hóa SĐT trước khi mã hóa: `+84 912 345 678` và `+84912345678` cho ra cùng token (đổi lại, giải mã trả về dạng đã chuẩn hóa) |
| `--mask-mentions` | [encrypt][transcript] che luôn các lần tên người nói được **nhắc trong lời thoại** (`"Colin and Rose, would you..."`), không chỉ nhãn người nói |
| `--strict` | [decrypt] dừng ngay khi gặp token không giải mã được |
| `--stdin` | đọc từ stdin, dùng trong pipeline |

## Cơ chế hoạt động

- **Thuật toán:** AES-256-SIV (RFC 5297) — chế độ AEAD *deterministic*, thiết kế riêng cho
  trường hợp không có nonce ngẫu nhiên.
- **Deterministic:** cùng một email luôn ra cùng một token, nên dữ liệu đã mã hóa vẫn
  `JOIN`, `GROUP BY`, đếm trùng lặp được như bình thường. Trong transcript, cùng một người nói
  luôn ra cùng token nên vẫn phân tích được ai nói bao nhiêu.
- **Ràng buộc ngữ cảnh:** mỗi loại có AAD riêng (domain cho email, `phone`, `speaker`), nên token
  không thể bị "dán" từ chỗ này sang chỗ khác để đánh lừa quá trình giải mã.
- **Toàn vẹn:** tag xác thực 16 byte — sai khóa hoặc dữ liệu bị sửa sẽ báo lỗi thay vì trả rác.
- **Idempotent:** chạy `encrypt` nhiều lần trên cùng file không mã hóa chồng lên nhau.

### Cách nhận diện

- **Email:** regex chuẩn; xử lý được cả ô chứa nhiều email (`a@x | b@x`).
- **Số điện thoại:** yêu cầu **9–15 chữ số**, chấp nhận `+`, khoảng trắng ngang, `-`, `.`, `()`.
  Ngưỡng này để tránh mã hóa nhầm mã số học sinh (`21657`) hay cột số đếm (`1`).
  Dấu phân cách **không** gồm xuống dòng, nên một số ở cuối đoạn không nuốt sang dòng sau.
- **Tên người nói** (chỉ trong transcript): ba dạng — `Tên:` đầu dòng, `0:01 - Tên` trên dòng riêng
  (bản xuất Google Meet / Otter / Teams), và thẻ WebVTT `<v Tên>`. Có danh sách loại trừ các từ khóa
  siêu dữ liệu (`Date`, `Attendees`, `Chủ đề`, `NOTE`…).
- **Tên được nhắc trong lời thoại**: mặc định **không** che. Bật `--mask-mentions` để che thêm các
  lần tên người nói xuất hiện giữa câu. Chỉ che tên đã nhận ra từ nhãn người nói, và bỏ qua những
  từ chung như `Speaker`, `Student` trong nhãn kiểu `Unidentified Speaker`.

## Giới hạn cần biết

- Local-part sau mã hóa dài hơn bản gốc (~26 ký tự + độ dài gốc × 1.6). Nếu local-part gốc dài
  hơn ~20 ký tự, token vượt giới hạn 64 ký tự của chuẩn email — chương trình vẫn xử lý nhưng
  in cảnh báo (dữ liệu phân tích thì không sao, đừng dùng token đó làm địa chỉ gửi thư thật).
- `.docx` round-trip đúng **nội dung** chứ không đúng từng byte (Word đóng gói lại file zip).
  Đoạn văn nào không chứa thông tin nhạy cảm thì được giữ nguyên tuyệt đối; đoạn có thay đổi
  sẽ bị gộp về định dạng của run đầu tiên.
- `.eml`: thư được dựng lại nên header có thể được chuẩn hóa. Nội dung khôi phục chính xác.
- Tên người **ngoài transcript** (cột `First Name` trong CSV chẳng hạn) không được mã hóa.
  Nếu cần ẩn danh hoàn toàn thì phải xử lý thêm các cột đó.
- File `--mapping` chứa dữ liệu gốc — bảo mật ngang với `.env`.

## Kiểm thử

```bash
python anonymize.py selftest
```

---

# organize — Đổi tên hàng loạt & sắp xếp tài liệu

**Luôn xem trước, không tự đổi gì** cho đến khi thêm `--apply`. Mọi thao tác đều hoàn tác được.

```
Biên bản họp Quý 3 (bản cuối).docx  ->  2026-07-14-bien-ban-hop-quy-3-ban-cuoi.docx
Tải về/Hợp đồng ABC.pdf             ->  tai-lieu/2026-02/hop-dong-abc.pdf
```

## Cấu trúc

```
organize.py                      lối tắt  ==  python -m tools.organize
tools/organize/
  kinds.py                       phân loại file theo đuôi  →  {kind}
  naming.py                      slugify tiếng Việt, làm sạch tên, dựng tên từ mẫu
  dates.py                       lấy ngày từ mtime / tên file / metadata tài liệu
  core.py                        quét file, dựng kế hoạch, thực thi an toàn
  journal.py                     nhật ký thao tác và hoàn tác
  cli.py                         dòng lệnh
  selftest.py                    kiểm thử nhanh
.agents/skills/organize/         skill + wrapper + references/architecture.md
```

## Đổi tên

```bash
python organize.py rename docs                                      # xem trước
python organize.py rename docs --template "{date}-{slug}{ext}" --date-from name --apply
```

`rename` đổi tên **tại chỗ** — kể cả với `-r`, file vẫn nằm nguyên thư mục của nó.

## Sắp xếp vào thư mục

```bash
python organize.py arrange docs -r --by kind-date --apply --prune
python organize.py arrange docs --into "{kind}/{year}-{month}/{name}{ext}" --apply
```

Lối tắt `--by`: `kind` · `date` · `kind-date` · `ext` · `year`.

## Hoàn tác

```bash
python organize.py undo docs --apply
```

Mỗi lần `--apply` ghi một phiên vào `docs/.organize-journal.jsonl`; `undo` lùi một phiên
mỗi lần gọi, nên chạy hai lần sẽ gỡ được cả `arrange` lẫn `rename` trước đó.

## Biến dùng trong mẫu

```bash
python organize.py fields
```

| Biến | Nghĩa |
|---|---|
| `{name}` `{slug}` | tên gốc / tên đã bỏ dấu, viết thường, nối bằng `-` |
| `{ext}` `{EXT}` | `.pdf` / `PDF` |
| `{date}` `{year}` `{month}` `{day}` | ngày của file |
| `{kind}` | `tai-lieu` `bang-tinh` `trinh-chieu` `hinh-anh` `video` `am-thanh` `bien-ban` `thu` `nen` `ma-nguon` `khac` |
| `{parent}` | tên thư mục chứa file |
| `{n}` | số thứ tự, `{n:03d}` ra `001` |
| `{hash}` | 8 ký tự SHA-256 nội dung — tiện phát hiện file trùng |

## Tùy chọn

| Cờ | Ý nghĩa |
|---|---|
| `--apply` | thực sự đổi (mặc định chỉ xem trước) |
| `-r` | xử lý cả thư mục con |
| `--include '*.pdf' '*.docx'` · `--exclude` | lọc file |
| `--date-from mtime\|name\|meta` | nguồn ngày; `name` đọc từ tên file, `meta` đọc metadata .docx/.pdf/.xlsx |
| `--on-conflict suffix\|skip\|fail` | khi tên đích đã tồn tại (mặc định `suffix`) |
| `--sep _` | dùng gạch dưới thay gạch ngang trong `{slug}` |
| `--sort name\|date\|size` · `--start N` | thứ tự và số bắt đầu cho `{n}` |
| `--prune` | [arrange] xóa thư mục rỗng còn lại |

## An toàn

- **Không bao giờ ghi đè** — trùng tên thì thêm hậu tố `-2`, `-3`…
- Mẫu không thể đưa file ra ngoài thư mục gốc (mọi đoạn đường dẫn đều được làm sạch).
- Nhật ký ghi sau **từng** thao tác, nên đứt giữa chừng vẫn hoàn tác được phần đã làm.
- `arrange` đổi cấu trúc thư mục — liên kết từ nơi khác tới file sẽ hỏng.

## Kiểm thử

```bash
python organize.py selftest
```


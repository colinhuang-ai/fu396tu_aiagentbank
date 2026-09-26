# Handlers

Mỗi định dạng một module trong `tools/anonymize/handlers/`. Handler chỉ lo **lấy văn bản ra**
và **đặt lại vào đúng chỗ cũ**; việc mã hóa do `encrypt.py` / `decrypt.py` làm.

| Module | `--kind` | Đuôi | Nền tảng |
|---|---|---|---|
| `plain.py` | `text` | `.csv .tsv .txt .json .xml .yaml .sql .md …` | stdlib |
| `xlsx.py` | `xlsx` | `.xlsx .xlsm` | openpyxl |
| `docx.py` | `docx` | `.docx` | python-docx |
| `pdf.py` | `pdf` | `.pdf` → `.txt` | pypdf |
| `transcript.py` | `transcript` | `.vtt .srt .sbv` + `.txt` tự đoán | stdlib |
| `eml.py` | `email` | `.eml .mbox` | stdlib `email` |

## Giao ước

```python
class Handler:
    name: str                      # định danh cho --kind
    label: str                     # tên hiển thị
    suffixes: tuple[str, ...]      # đuôi file nhận tự động
    output_suffix: str | None      # ép đuôi file ra (pdf → ".txt"); None = giữ nguyên
    binary: bool                   # True = không xem trước dạng văn bản được

    def process(self, raw: bytes, cipher, mode, strict=False) -> bytes: ...
    def preview(self, raw: bytes) -> str | None: ...
```

`TextHandler` đã lo sẵn BOM / CRLF; định dạng văn bản có cấu trúc riêng chỉ cần ghi đè
`transform()` (xem `transcript.py`).

## Cách chọn handler

`handlers/get_handler(filename, raw, kind)`:

1. `kind != "auto"` → dùng đúng handler đó.
2. Khớp theo đuôi file.
3. Nếu ra `PlainHandler` và có `raw` → đoán thêm nội dung xem có phải transcript không.

Đoán transcript (`transcript.is_transcript`): có `WEBVTT` ở đầu, có thẻ `<v ...>`, hoặc
≥ 3 dòng dạng `Tên:` và chiếm ≥ 20% số dòng.

## Ghi chú từng handler

**plain** — thay theo nội dung nên không phá cấu trúc cột; một ô chứa nhiều email
(`a@x | b@x`) vẫn được thay từng cái. Round-trip đúng từng byte.

**xlsx** — duyệt mọi sheet, chỉ đụng ô kiểu `str`. Ô số, ngày, công thức và định dạng bảng
giữ nguyên.

**docx** — Word cắt một đoạn văn thành nhiều "run" theo định dạng, nên một email có thể bị
xé làm ba (`lore` + `toa@isb` + `.ac.th`). Handler **gộp toàn bộ `w:t` của đoạn** rồi mới xử
lý. Đoạn nào thực sự thay đổi mới dồn kết quả vào run đầu tiên (mất định dạng nội bộ của
riêng đoạn đó); đoạn không đụng tới thì giữ nguyên tuyệt đối. Quét cả bảng, text box,
đầu trang và chân trang. Round-trip đúng **nội dung**, không đúng từng byte (zip đóng lại).

**pdf** — PDF đặt chữ theo tọa độ tuyệt đối nên không sửa tại chỗ mà không phá bố cục.
Handler trích văn bản, mã hóa, xuất `.txt`. **Một chiều**: `mode="decrypt"` trên `.pdf` báo
lỗi và chỉ người dùng giải mã từ `.txt`. PDF scan không có lớp văn bản → báo lỗi gợi ý OCR.

**transcript** — ngoài email/SĐT còn mã hóa **tên người nói**:

```
Nguyen Van A: xin chao        →  enc1n<token>: xin chao
[00:12] Tran Thi B: vang      →  [00:12] enc1n<token>: vang
<v Le Van C>noi gi do</v>     →  <v enc1n<token>>noi gi do</v>
```

Nhận ba dạng nhãn người nói: `Tên:` đầu dòng, `0:01 - Tên` trên dòng riêng (bản xuất Google Meet /
Otter / Teams — không có dấu hai chấm nên dạng đầu không bắt được), và thẻ WebVTT `<v Tên>`.
Dạng "chiếm trọn dòng" được nới lỏng kiểm tra vì không thể nhầm với nội dung khác: chấp nhận cả
`Nika@MARIO` hay `SPH Student Supp. Serv.`.

`--mask-mentions` bật thêm một lượt nữa: che các lần tên người nói được **nhắc giữa lời thoại**.
Ứng viên dựng từ chính danh sách nhãn đã nhận ra — luôn lấy nhãn đầy đủ, chỉ tách lấy từng từ khi
nhãn trông giống tên người thật (2–3 từ viết hoa, toàn chữ cái), và bỏ qua `NOT_A_NAME`
(`Speaker`, `Student`, `Support`…) để không che nhầm từ chung.

Mốc thời gian và số thứ tự cue giữ nguyên. Cùng một người nói luôn ra cùng token nên vẫn
phân tích được ai nói bao nhiêu. Có danh sách loại trừ (`METADATA_KEYS`) để `Date:`,
`Attendees:`, `NOTE`, `Chủ đề:`… không bị nhận nhầm là tên người. Chiều giải mã không cần
biết cấu trúc — `decrypt_text` tự nhận mọi token.

**eml** — xử lý có cấu trúc thay vì quét văn bản thô, vì thân thư thường mã hóa base64 /
quoted-printable (quét thô sẽ bỏ sót hoàn toàn). Xử lý header địa chỉ (cả tên hiển thị lẫn
địa chỉ), `Subject`, và mọi phần thân `text/*` sau khi giải transfer-encoding. Tệp đính kèm
nhị phân giữ nguyên. `.msg` nhị phân của Outlook chưa hỗ trợ — báo lỗi kèm gợi ý lưu sang
`.eml`.

## Thêm handler mới

1. Tạo `tools/anonymize/handlers/<tên>.py`, kế thừa `Handler` (hoặc `TextHandler` nếu là
   văn bản), đặt `name`, `label`, `suffixes`.
2. Thư viện ngoài thì `import` **bên trong** `process()` và bắt `ImportError` thành
   `AnonymizeError` kèm câu lệnh `pip install` — để người không dùng định dạng đó không
   phải cài thêm gì.
3. Đăng ký vào `HANDLERS` trong `handlers/__init__.py`.
4. Thêm phụ thuộc vào `requirements.txt`, đánh dấu là tùy chọn.

Handler mới tự động xuất hiện ở `--kind`, lệnh `kinds` và ô chọn trên giao diện web —
không phải sửa `cli.py` hay `server.py`.

Khuôn mẫu ngắn nhất:

```python
from ..core import AnonymizeError, Cipher
from .base import Handler, transform_text


class RtfHandler(Handler):
    name = "rtf"
    label = "Rich Text (.rtf)"
    suffixes = (".rtf",)
    binary = True

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        ...  # lấy văn bản ra, gọi transform_text(), đặt lại vào chỗ cũ
```

---
name: anonymize
description: Mã hóa / giải mã (reversible) email, số điện thoại và tên người nói trong tài liệu — CSV, TSV, TXT, JSON, Excel, Word, PDF, biên bản họp (.vtt/.srt) và thư .eml. Dùng khi người dùng muốn ẩn danh dữ liệu, che thông tin cá nhân (PII) trước khi chia sẻ / gửi cho bên thứ ba / đưa vào LLM, hoặc muốn khôi phục lại dữ liệu đã ẩn danh. Kích hoạt cả khi người dùng nói "ẩn danh file này", "che email trước khi gửi", "mask PII", "giải mã lại file đã ẩn danh", "gỡ thông tin cá nhân khỏi biên bản họp".
---

# anonymize

Ẩn danh **có thể đảo ngược**: mỗi giá trị nhạy cảm được thay bằng một token, và giải mã lại
được nguyên vẹn bằng khóa trong `.env`.

```
loretoa@isb.ac.th   ->   enc1eiyclj7gfikdtquu6fc7gdg5jw55tocciu2rjy@isb.ac.th
+84 912 345 678     ->   enc1p3m2qsioyphzd2d4d26xvlktxaoy4zn6u7vyzlh5v7dsn4mskqi
Nguyen Van An:      ->   enc1nndgiwyvvf6l2uzftlxcne4tiqdtfaqz53zduqyx7lgvl5eq:
```

Domain email được giữ nguyên (`@isb.ac.th`) để vẫn thống kê được theo tổ chức.

## Quy trình

**1. Đảm bảo có khóa** — nếu chưa có `.env`:

```bash
python .agents/skills/anonymize/scripts/anonymize.py genkey
```

Nhắc người dùng sao lưu `.env`: mất khóa là không giải mã lại được. Không bao giờ commit `.env`,
không in nội dung khóa ra màn hình.

**2. Mã hóa:**

```bash
python .agents/skills/anonymize/scripts/anonymize.py encrypt -i <file> --mapping map.csv
```

**3. Kiểm tra trước khi giao kết quả** — luôn mở `map.csv` xem có gì bị bắt nhầm không
(mã số ≥ 9 chữ số dễ bị nhận nhầm thành số điện thoại). Nếu có, chạy lại và nói rõ cho người dùng.

**4. Giải mã:**

```bash
python .agents/skills/anonymize/scripts/anonymize.py decrypt -i <file.enc.csv> --strict
```

Luôn dùng `--strict` khi giải mã, để token hỏng báo lỗi thay vì âm thầm bị bỏ qua.

## Loại file

Nhận tự động theo đuôi file; `.txt` còn được đoán thêm theo nội dung (biên bản họp).
Ép tay bằng `--kind`:

| `--kind` | Đuôi | Ghi chú |
|---|---|---|
| `text` | `.csv .tsv .txt .json .xml .yaml .sql .md` | giữ nguyên BOM và CRLF |
| `xlsx` | `.xlsx .xlsm` | chỉ đụng ô kiểu chuỗi |
| `docx` | `.docx` | gộp run nên bắt được email bị Word xé nhỏ |
| `pdf` | `.pdf` | **xuất ra `.txt`**, một chiều |
| `transcript` | `.vtt .srt .sbv` + `.txt` | mã hóa thêm **tên người nói**; thêm `--mask-mentions` để che cả tên được nhắc giữa lời thoại |
| `email` | `.eml .mbox` | cả header lẫn thân base64 / quoted-printable |

```bash
python .agents/skills/anonymize/scripts/anonymize.py kinds       # liệt kê
python .agents/skills/anonymize/scripts/anonymize.py encrypt -i bien-ban.txt --kind transcript
```

## Giao diện web

Khi người dùng muốn tự kéo thả nhiều file:

```bash
python .agents/skills/anonymize/scripts/anonymize.py serve
```

Chạy ở `http://127.0.0.1:8765`, chỉ lắng nghe localhost. Đây là lệnh chạy nền lâu dài —
khởi động ở chế độ background rồi đưa link cho người dùng, đừng chờ nó kết thúc.

## Dùng như thư viện

```python
from tools.anonymize import Cipher, resolve_key, process_bytes

cipher = Cipher(resolve_key(".env"))
out = process_bytes(raw, "data.csv", cipher, "encrypt")
print(len(cipher.mapping), "giá trị đã xử lý")
```

## Điều phải nói với người dùng

- `map.csv` chứa dữ liệu gốc — bảo mật ngang `.env`, đừng gửi kèm file đã mã hóa.
- `.docx` và `.eml` khôi phục đúng **nội dung** nhưng không đúng từng byte.
- PDF là một chiều: mã hóa ra `.txt`, giải mã từ chính `.txt` đó chứ không quay lại PDF.
- Tên người **ngoài** transcript (cột `First Name` trong CSV) **không** được mã hóa.
- Với biên bản họp, mặc định chỉ che **nhãn người nói**. Tên được nhắc giữa câu vẫn còn — hãy chủ động
  nhắc người dùng và đề xuất `--mask-mentions`. Người chưa từng phát biểu thì kể cả cờ đó cũng không che được.

## Tham khảo thêm

- `references/architecture.md` — kiến trúc module, cách hoạt động của AES-SIV, định dạng token.
- `references/handlers.md` — chi tiết từng handler và **cách viết handler cho định dạng mới**.

Đọc hai file này khi cần sửa mã nguồn hoặc thêm định dạng; dùng thông thường thì không cần.

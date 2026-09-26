# Kiến trúc

## Bản đồ module

```
tools/anonymize/
  core.py         khóa (.env), nguyên thủy AES-SIV, lớp Cipher      ← không biết gì về email/SĐT
  encrypt.py      nhận diện + mã hóa email / SĐT / tên người
  decrypt.py      tìm token + khôi phục giá trị gốc
  fileio.py       điều phối: chọn handler, đặt tên file ra, bảng đối chiếu
  cli.py          dòng lệnh
  server.py       web server (chỉ stdlib) + web/index.html
  selftest.py     kiểm thử nhanh
  handlers/       mỗi định dạng một module — xem references/handlers.md
```

Chiều phụ thuộc một chiều, không có vòng lặp:

```
cli / server  →  fileio  →  handlers/*  →  encrypt, decrypt  →  core
```

`core.py` cố tình **không** biết email hay số điện thoại là gì — nó chỉ giữ khóa và làm
AEAD. Nhờ vậy thêm một loại dữ liệu nhạy cảm mới không phải đụng vào phần mật mã.

## Thuật toán

**AES-256-SIV (RFC 5297)** — AEAD *deterministic*, thiết kế riêng cho trường hợp không có
nonce ngẫu nhiên.

Vì sao không dùng AES-GCM: GCM cần nonce ngẫu nhiên cho mỗi lần mã hóa, nên cùng một email
sẽ ra hai token khác nhau ở hai dòng — mất khả năng `JOIN` / `GROUP BY` / đếm trùng lặp trên
dữ liệu đã ẩn danh. SIV đánh đổi: chấp nhận lộ thông tin "hai ô này giống nhau" để giữ được
tính dùng được của dữ liệu. Với bảng danh sách người thì đây là đánh đổi đúng.

Hệ quả cần biết: kẻ tấn công biết trước một email cụ thể **có thể kiểm chứng** email đó có
trong file hay không (mã hóa thử rồi so token). Đây là đặc tính cố hữu của mọi sơ đồ
deterministic, không phải lỗi cài đặt.

## Định dạng token

```
enc1 e ho4ngjluhc767juyfdoaat3t7agjvk66orvd6
│    │ └─ base32 thường (a-z2-7) của: tag 16 byte + ciphertext
│    └─── loại: e = email, p = số điện thoại, n = tên người
└──────── phiên bản định dạng
```

Base32 thường được chọn vì hợp lệ trong local-part của email và an toàn trong CSV
(không có dấu phẩy, nháy, xuống dòng).

Token email giữ domain ở ngoài: `enc1e<token>@isb.ac.th`.

## AAD — ràng buộc ngữ cảnh

Mỗi loại đưa một *associated data* khác nhau vào AEAD:

| Loại | AAD |
|---|---|
| email | domain viết thường (`isb.ac.th`) |
| số điện thoại | `phone` |
| tên người | `speaker` |

Nên token của `a@x.com` không thể bị "dán" sang `@y.com` để đánh lừa quá trình giải mã —
đổi domain là tag xác thực sai ngay.

## Khóa

`core.resolve_key()` lấy khóa theo thứ tự:

1. `ANONYMIZE_KEY` — base64 của 32/48/64 byte (biến môi trường **hoặc** `.env`)
2. `ANONYMIZE_PASSPHRASE` + `ANONYMIZE_SALT` — dẫn xuất bằng scrypt (n=2^15, r=8, p=1)

Biến môi trường được ưu tiên hơn file, tiện cho CI.

## Bất biến cần giữ khi sửa code

- **Idempotent**: chạy `encrypt` lại trên dữ liệu đã mã hóa không được mã hóa chồng lên.
  Đảm bảo bởi nhánh `token` đứng **đầu tiên** trong `_SCAN_RE` của `encrypt.py`.
- **Quét một lần**: mọi phép thay thế phải nằm trong một lượt `re.sub` duy nhất, để token vừa
  sinh ra không bị quét lại.
- **Không nuốt xuống dòng**: dấu phân cách trong `PHONE_RE` chỉ gồm khoảng trắng ngang.
  Nếu cho `\s`, một số điện thoại cuối đoạn sẽ nuốt sang các dòng sau (đã từng là lỗi thật
  với file `.vtt`: nuốt luôn mốc thời gian của cue kế tiếp). Có kiểm thử hồi quy trong
  `selftest.py`.
- **Bảo toàn byte**: handler văn bản phải giữ BOM và kiểu xuống dòng gốc. Đọc bằng
  `raw.decode("utf-8-sig")` chứ không dùng `Path.read_text()` — hàm đó đổi CRLF thành LF.

## Kiểm thử

```bash
python anonymize.py selftest
```

Chạy sau mọi thay đổi ở `core`, `encrypt`, `decrypt`. Kiểm tra: round-trip, giữ domain,
deterministic, idempotent, không đụng số ngắn, không nuốt xuống dòng, sai khóa thì thất bại.

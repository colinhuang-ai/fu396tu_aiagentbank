# anonymize — Mã hóa / giải mã email & số điện thoại

Công cụ CLI mã hóa các thông tin nhạy cảm (email, số điện thoại) trong file dữ liệu,
**giữ nguyên cấu trúc file** và **cho phép giải mã ngược lại** khi cần trích xuất.

```
loretoa@isb.ac.th   ->   enc1ean3jianix45crojby7mgnjfrzpnq7gbn4gvts@isb.ac.th
+84 912 345 678     ->   enc1pqzapr2suopos7zye4u33knkg5i5v7ctr7vowr5ncn4ps5vfyzi
```

Domain (`@isb.ac.th`) được giữ nguyên để bạn vẫn thống kê được theo tổ chức;
chỉ phần định danh cá nhân (local-part) bị mã hóa.

## Cài đặt

```bash
pip install -r requirements.txt
```

## 1. Tạo khóa

```bash
python anonymize.py genkey
```

Lệnh này tạo file `.env` chứa `ANONYMIZE_KEY` (64 byte ngẫu nhiên, base64).

> **Quan trọng:** sao lưu `.env` ở nơi an toàn. Mất khóa = không giải mã lại được.
> File `.gitignore` đã loại `.env` khỏi git.

## 2. Mã hóa

```bash
python anonymize.py encrypt -i students.tsv -o students.enc.tsv
```

Mã hóa trực tiếp một chuỗi (tiện để kiểm tra nhanh):

```bash
python anonymize.py encrypt -t "Cindy	BAO	loretoa@isb.ac.th | miokc@isb.ac.th"
```

Xuất kèm bảng đối chiếu gốc → token:

```bash
python anonymize.py encrypt -i students.tsv --mapping map.csv
```

## 3. Giải mã

```bash
python anonymize.py decrypt -i students.enc.tsv -o students.tsv
```

Kết quả trùng khớp **byte-by-byte** với file gốc.

## Định dạng hỗ trợ

| Loại | Ghi chú |
|---|---|
| `.tsv` `.csv` `.txt` `.json` `.sql` … | mọi file văn bản, xử lý theo nội dung nên không phá cấu trúc cột |
| `.xlsx` `.xlsm` | quét mọi sheet / mọi ô kiểu chuỗi, giữ nguyên định dạng bảng |

## Tùy chọn

| Cờ | Ý nghĩa |
|---|---|
| `--env <path>` | dùng file `.env` khác (nhiều môi trường / nhiều khóa) |
| `--mapping <file.csv>` | [encrypt] xuất bảng đối chiếu gốc → token |
| `--normalize-phone` | [encrypt] chuẩn hóa số điện thoại trước khi mã hóa: `+84 912 345 678` và `+84912345678` cho ra cùng một token (đổi lại, giải mã trả về dạng đã chuẩn hóa) |
| `--strict` | [decrypt] dừng ngay khi gặp token không giải mã được, thay vì bỏ qua |
| `--stdin` | đọc từ stdin, dùng trong pipeline |

## Cơ chế hoạt động

- **Thuật toán:** AES-256-SIV (RFC 5297) — chế độ AEAD *deterministic*, được thiết kế
  riêng cho trường hợp không có nonce ngẫu nhiên.
- **Deterministic:** cùng một email luôn ra cùng một token, nên dữ liệu đã mã hóa
  vẫn `JOIN`, `GROUP BY`, đếm trùng lặp được như bình thường.
- **Ràng buộc ngữ cảnh:** domain được đưa vào AAD (associated data), nên token của
  `a@x.com` không thể bị "dán" sang `@y.com` để đánh lừa quá trình giải mã.
- **Toàn vẹn:** tag xác thực 16 byte — dữ liệu bị sửa đổi hoặc sai khóa sẽ báo lỗi
  thay vì trả ra kết quả rác.
- **Mã hóa một lần:** chạy `encrypt` nhiều lần trên cùng file không mã hóa chồng lên nhau.

### Cách nhận diện dữ liệu nhạy cảm

- **Email:** regex chuẩn; xử lý được cả ô chứa nhiều email (`a@x | b@x`).
- **Số điện thoại:** yêu cầu **9–15 chữ số**, chấp nhận `+`, khoảng trắng, `-`, `.`, `()`.
  Ngưỡng này để tránh mã hóa nhầm mã số học sinh (`21657`) hay cột số đếm (`1`).
  Nếu dữ liệu của bạn có mã số ≥ 9 chữ số, nên rà lại file `--mapping` sau lần chạy đầu.

## Giới hạn cần biết

- Local-part sau mã hóa dài hơn bản gốc (~26 ký tự + độ dài gốc × 1.6). Nếu local-part
  gốc dài hơn ~20 ký tự, token sẽ vượt giới hạn 64 ký tự của chuẩn email — chương trình
  vẫn xử lý nhưng in cảnh báo (dữ liệu phân tích thì không sao, nhưng đừng dùng token
  đó làm địa chỉ gửi thư thật).
- Tên người (`Cindy`, `BAO`), mã số học sinh, ngày sinh… **không** được mã hóa.
  Nếu cần ẩn danh hoàn toàn thì phải xử lý thêm các cột đó.
- File `--mapping` chứa dữ liệu gốc — bảo mật nó ngang với `.env`.

## Kiểm thử

```bash
python anonymize.py selftest
```

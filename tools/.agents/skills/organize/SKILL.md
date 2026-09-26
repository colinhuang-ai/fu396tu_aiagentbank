---
name: organize
description: Đổi tên file hàng loạt và sắp xếp tài liệu vào thư mục theo loại / ngày / mẫu tự đặt. Chuẩn hóa tên tiếng Việt có dấu thành slug ASCII, đọc ngày từ tên file hoặc metadata tài liệu, luôn xem trước rồi mới đổi, và hoàn tác được. Dùng khi người dùng nói "đổi tên đống file này", "sắp xếp lại thư mục", "gom tài liệu theo tháng", "bỏ dấu tên file", "dọn thư mục Tải về", "đánh số lại ảnh", "undo vừa nãy đổi tên".
---

# organize

Đổi tên hàng loạt và sắp xếp tài liệu. **Luôn xem trước, không tự đổi gì** cho đến khi có `--apply`.

```
Biên bản họp Quý 3 (bản cuối).docx  ->  2026-07-14-bien-ban-hop-quy-3-ban-cuoi.docx
Tải về/Hợp đồng ABC.pdf             ->  tai-lieu/2026-02/hop-dong-abc.pdf
```

## Quy tắc bắt buộc

1. **Luôn chạy xem trước trước** (bỏ `--apply`), đọc kỹ danh sách, rồi mới chạy lại với `--apply`.
   Với thư mục nhiều file hoặc tài liệu quan trọng, đưa bản xem trước cho người dùng duyệt trước.
2. **Nhắc người dùng cách hoàn tác** sau mỗi lần `--apply` — lệnh in sẵn ở cuối.
3. Không bao giờ chạy trên thư mục gốc của ổ đĩa, thư mục người dùng, hay cây mã nguồn
   trừ khi người dùng nói rõ. Hỏi lại nếu thư mục có vẻ quá rộng.

## Lệnh

```bash
python .agents/skills/organize/scripts/organize.py rename  <thư-mục> [--template MAU]
python .agents/skills/organize/scripts/organize.py arrange <thư-mục> [--by LOAI | --into MAU]
python .agents/skills/organize/scripts/organize.py undo    <thư-mục> [--apply]
python .agents/skills/organize/scripts/organize.py fields    # các biến dùng trong mẫu
python .agents/skills/organize/scripts/organize.py kinds     # các nhóm tài liệu
```

`rename` đổi tên **tại chỗ** — kể cả khi chạy `-r`, file vẫn nằm nguyên thư mục của nó.
`arrange` mới là lệnh chuyển file sang thư mục khác.

## Mẫu tên

| Biến | Nghĩa |
|---|---|
| `{name}` | tên gốc (không đuôi) |
| `{slug}` | tên gốc đã bỏ dấu, viết thường, nối bằng `-` |
| `{ext}` `{EXT}` | `.pdf` / `PDF` |
| `{date}` `{year}` `{month}` `{day}` | ngày của file |
| `{kind}` | nhóm: `tai-lieu`, `bang-tinh`, `hinh-anh`, `bien-ban`, `thu`… |
| `{parent}` | tên thư mục chứa file |
| `{n}` | số thứ tự, `{n:03d}` ra `001` |
| `{hash}` | 8 ký tự SHA-256 nội dung — tiện phát hiện file trùng |

Mẫu hay dùng:

```bash
--template "{slug}{ext}"                 # chỉ bỏ dấu, chuẩn hóa tên (mặc định)
--template "{date}-{slug}{ext}"          # thêm ngày lên đầu để sắp theo thời gian
--template "{n:03d}-{slug}{ext}"         # đánh số 001, 002, ...
```

Lối tắt cho `arrange --by`: `kind`, `date`, `kind-date`, `ext`, `year`.
Cần khác thì dùng `--into "{kind}/{year}-{month}/{name}{ext}"`.

## Nguồn ngày

`--date-from mtime` (mặc định) · `name` (đọc ngày từ chính tên file) · `meta` (ngày tạo
trong metadata .docx/.pdf/.xlsx). `name` và `meta` tự quay về `mtime` khi không tìm thấy.

Với thư mục tải về hoặc ảnh chụp, `--date-from name` thường đúng hơn `mtime` (mtime là
lúc tải về chứ không phải lúc tạo tài liệu).

## Cờ hay dùng

| Cờ | Ý nghĩa |
|---|---|
| `--apply` | thực sự đổi (mặc định chỉ xem trước) |
| `-r` | xử lý cả thư mục con |
| `--include '*.pdf' '*.docx'` | chỉ lấy file khớp mẫu |
| `--exclude` | bỏ qua file khớp mẫu |
| `--on-conflict suffix\|skip\|fail` | khi tên đích đã tồn tại (mặc định `suffix`) |
| `--sep _` | dùng gạch dưới thay gạch ngang trong `{slug}` |
| `--prune` | [arrange] xóa thư mục rỗng còn lại |

## Hoàn tác

Mỗi lần `--apply` ghi một phiên vào `<thư-mục>/.organize-journal.jsonl`. `undo` lùi một
phiên mỗi lần gọi, nên chạy hai lần sẽ lùi được cả `arrange` lẫn `rename` trước đó.

```bash
python .agents/skills/organize/scripts/organize.py undo <thư-mục>          # xem trước
python .agents/skills/organize/scripts/organize.py undo <thư-mục> --apply  # thực hiện
```

Nếu người dùng đã tự di chuyển/xóa file sau đó, `undo` báo cảnh báo cho từng file và bỏ
qua file đó chứ không làm hỏng thêm.

## Điều phải nói với người dùng

- Tên trùng thì **thêm hậu tố** (`bao-cao-2.pdf`), không bao giờ ghi đè.
- `arrange` làm thay đổi cấu trúc thư mục — nếu file đang được liên kết từ nơi khác
  (script, shortcut, tài liệu khác) thì các liên kết đó sẽ hỏng.
- Nhật ký `.organize-journal.jsonl` cần giữ lại thì mới hoàn tác được.

## Dùng chung với `anonymize`

Nhóm `bien-ban` (`.vtt .srt`) và `thu` (`.eml`) khớp đúng các định dạng mà skill
`anonymize` xử lý được. Quy trình hay gặp: `arrange --by kind` để gom biên bản họp lại,
rồi chạy `anonymize` trên thư mục đó trước khi chia sẻ.

## Tham khảo thêm

- `references/architecture.md` — kiến trúc module, quy tắc an toàn, cách thêm biến mới.

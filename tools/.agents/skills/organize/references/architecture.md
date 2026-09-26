# Kiến trúc

## Bản đồ module

```
tools/organize/
  kinds.py      phân loại file theo đuôi  →  {kind}
  naming.py     slugify tiếng Việt, làm sạch tên, dựng tên từ mẫu
  dates.py      lấy ngày từ mtime / tên file / metadata tài liệu
  core.py       quét file, dựng kế hoạch, thực thi an toàn
  journal.py    nhật ký thao tác và hoàn tác
  cli.py        dòng lệnh
  selftest.py   kiểm thử nhanh
```

Chiều phụ thuộc một chiều: `cli → core → naming, dates, kinds`. `journal` chỉ phụ thuộc
vào kiểu `Action` của `core`.

## Luồng xử lý

```
collect()     quét file, lọc theo --include/--exclude, bỏ file ẩn và thư mục rác
sort_files()  sắp thứ tự (quyết định {n})
build_plan()  dựng danh sách Action(src → dst), giải quyết trùng tên, kiểm tra an toàn
execute()     dọn vào đĩa, ghi nhật ký sau TỪNG bước
```

Kế hoạch được dựng trọn vẹn và kiểm tra xong mới chạm vào đĩa. Không có `--apply` thì
dừng lại ở `build_plan()`.

## `anchor` — điểm neo của mẫu

Mẫu cho ra một đường dẫn **tương đối**. Nó tương đối so với đâu là khác biệt giữa hai lệnh:

| Lệnh | `anchor` | Nghĩa |
|---|---|---|
| `rename` | `parent` | tương đối với thư mục đang chứa file → file ở nguyên chỗ |
| `arrange` | `root` | tương đối với thư mục gốc → file được chuyển thư mục |

Không có phân biệt này thì `rename -r` sẽ kéo hết file ở thư mục con về thư mục gốc —
đây từng là lỗi thật, hiện có kiểm thử hồi quy.

## Quy tắc an toàn (không được phá khi sửa code)

- **Không bao giờ ghi đè.** Trùng tên thì theo `--on-conflict`: `suffix` (mặc định),
  `skip`, hoặc `fail`. Kiểm tra cả file đã có trên đĩa lẫn tên đã bị một Action khác
  trong cùng kế hoạch chiếm (`taken`).
- **Không thoát ra ngoài thư mục gốc.** `naming.render()` làm sạch từng đoạn đường dẫn,
  nên `{name}` chứa `../..` cũng không ra được ngoài; `build_plan()` kiểm tra lại lần nữa.
- **Xem trước là mặc định.** Chỉ `--apply` mới gọi `execute()`.
- **Ghi nhật ký sau từng bước**, không phải sau cả lô — đứt giữa chừng vẫn hoàn tác được.

## Bẫy trên Windows (đã gặp thật)

`pathlib.Path` so sánh **không phân biệt hoa/thường** trên Windows, và `Path.resolve()`
trả về đúng hoa/thường đang có trên đĩa. Hai điều đó cộng lại khiến đổi tên kiểu
`BAOCAO.TXT` → `baocao.txt` bị coi là "không có gì thay đổi" và âm thầm bị bỏ qua.

Cách xử lý hiện tại, đừng sửa lại:

- `build_plan()` dùng `os.path.abspath()` chứ **không** dùng `.resolve()`.
- `Action.is_noop` / `is_move` so sánh bằng **chuỗi**, không bằng `Path`.
- `core._move()` đổi tên qua một bước trung gian khi nguồn và đích là cùng một file
  trên đĩa (đổi tên chỉ khác hoa/thường), vì hệ thống không cho đổi trực tiếp.

Có kiểm thử hồi quy cho cả ba điểm này.

## Nhật ký

`.organize-journal.jsonl` — mỗi dòng một bản ghi JSON:

```json
{"type": "session", "at": "2026-09-19T09:58:28", "command": "arrange docs --template ..."}
{"type": "move", "at": "2026-09-19T09:58:28", "src": "...", "dst": "..."}
```

`undo_last()` lấy phiên cuối cùng còn bản ghi `move`, đi ngược thứ tự, trả file về chỗ cũ,
rồi **xóa phiên đó khỏi nhật ký** — nên gọi `undo` nhiều lần sẽ lùi được nhiều bước.

File đích không còn, hoặc chỗ cũ đã bị chiếm → ghi cảnh báo và bỏ qua file đó, không
làm hỏng thêm.

## Thêm biến mới cho mẫu

1. Thêm khóa vào dict trả về của `core.fields_for()`.
2. Thêm một dòng mô tả vào `core.describe_fields()` (lệnh `fields` tự hiện ra).
3. Nếu tính toán tốn kém (đọc cả file như `{hash}`), làm lười giống `need_hash`:
   `build_plan()` dùng `naming.placeholders()` để biết mẫu có dùng biến đó không.

Giá trị kiểu chuỗi được `naming.render()` làm sạch tự động, nên không phải tự lo ký tự lạ.

## Kiểm thử

```bash
python organize.py selftest
```

Dựng cây thư mục tạm với tên tiếng Việt có dấu, chạy đủ vòng đổi tên → sắp xếp → hoàn tác,
rồi kiểm tra từng bất biến ở trên. Chạy lại sau mọi thay đổi trong `core` hoặc `naming`.

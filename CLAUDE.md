\# QUY TẮC ĐẶT TÊN FILE



Mọi file bạn tạo, export hoặc đề xuất tên đều phải theo chuẩn dưới đây.

Không tự chế biến thể khác. Không hỏi lại nếu đã đủ thông tin để suy ra.



\## Cú pháp



<MaKH>\_<TenTaiLieu>\_<YYYYMMDD>\_<Author>\_<Version>.<ext>



Ví dụ: VCB\_BaoCaoAds\_20260930\_CLN\_v1.0.xlsx



\## Trường



| Trường     | Quy tắc |

|------------|---------|

| MaKH       | 2–5 ký tự IN HOA. Nội bộ = INT. Dùng chung nhiều khách = MULTI |

| TenTaiLieu | PascalCase, không dấu, không space, ≤40 ký tự. Mô tả nội dung, KHÔNG mô tả trạng thái |

| YYYYMMDD   | Ngày hiệu lực / kỳ dữ liệu, KHÔNG phải ngày tạo file. Theo tháng dùng YYYYMM |

| Author     | Mã 2–4 ký tự của người sửa gần nhất. Mặc định: CLN |

| Version    | v<major>.<minor>, luôn đủ 2 phần (v1.0, không phải v1) |



Ký tự cho phép: A-Z a-z 0-9 \_ - .

`\_` ngăn trường, `-` ngăn từ trong cùng một trường.



\## Bỏ trường ngày khi nào



\- Living document (quy trình, chính sách, template, hướng dẫn) → BỎ YYYYMMDD

\- Gắn với thời điểm (báo cáo, biên bản, export, hợp đồng, đề xuất) → GIỮ



\## Version



\- v0.x = draft. v1.0 trở lên = đã duyệt.

\- Sửa nội dung/typo/format → +0.1 minor

\- Viết lại, đổi cấu trúc, tái phát hành → +1 major, reset minor về 0

\- Ngày mới KHÔNG đồng nghĩa version mới. Cùng kỳ dữ liệu mà sửa nhiều lần:

&#x20; giữ nguyên ngày, chỉ tăng version.



\## Cấm



\- FINAL, final2, moinhat, banchuan, copy, (1), " - Copy"

\- Dấu tiếng Việt, khoảng trắng, \\ / : \* ? " < > | và emoji

\- Đặt tên theo người nhận

\- Đổi tên file người khác gửi tới (giữ nguyên tên gốc)



\## Hành vi bắt buộc



1\. Khi tạo file: tự suy `TenTaiLieu`, `YYYYMMDD`, `Version` từ ngữ cảnh.

&#x20;  Version mặc định v1.0 nếu là bản đầu và không phải draft.

2\. Nếu thiếu `MaKH` và không suy được từ ngữ cảnh → hỏi đúng 1 câu,

&#x20;  không tự bịa mã.

3\. Nếu tôi đưa tên file sai chuẩn → sửa lại theo chuẩn và nói ngắn gọn đã sửa gì.

&#x20;  Không im lặng làm theo tên sai.

4\. Khi tạo version tiếp theo của file đã có: nhắc tôi đẩy bản cũ sang 03\_Archive.

5\. Không bao giờ đề xuất ghi đè file đã ở trạng thái Released (major ≥ 1).



\## Thư mục



/Clients/<MaKH>/01\_Working | 02\_Released | 03\_Archive | 99\_Input

/Internal/01\_Working | ...



\- 01\_Working chỉ giữ MỘT file cho mỗi TenTaiLieu

\- 02\_Released read-only

\- 99\_Input giữ nguyên tên gốc file nhận từ ngoài


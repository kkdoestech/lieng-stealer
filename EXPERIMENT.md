# ***ĐÁNH BẠI "NHÀ CÁI" TRONG ĐÊM CÙNG LÝ THUYẾT TRÒ CHƠI VÀ AI PAIR PROGRAMMING***

*\*P.S: Đây là educational project, không phải financial advice.\**

*Tuyên bố từ chối trách nhiệm (Disclaimer): Dự án được thực hiện hoàn toàn cho mục đích nghiên cứu học thuật về Khoa học máy tính, Lý thuyết trò chơi và Cấu trúc dữ liệu & Giải thuật. Nhóm tác giả kiên quyết phản đối mọi hành vi cờ bạc và cá độ dưới mọi hình thức.\**

# 

# **BÁO CÁO ĐỀ TÀI: NGHIÊN CỨU & XÂY DỰNG HỆ THỐNG TỐI ƯU HÓA CHIẾN THUẬT RA QUYẾT ĐỊNH TRONG TRÒ CHƠI LIÊNG (LIÊNG STEALER)**

## **1\. Đặt Vấn Đề & Mục Tiêu Đề Tài (Problem Statement & Objectives)**

Trong lý thuyết trò chơi (Game Theory), các trò chơi bài thuộc nhóm **Trò chơi có thông tin không hoàn hảo (Imperfect Information Games)**, nơi người chơi phải đưa ra quyết định tối ưu dưới điều kiện bất định. Đề tài **Liêng Stealer** tập trung vào việc nghiên cứu và ứng dụng xác suất thống kê cùng mô hình Kỳ vọng Toán học (Expected Value \- EV) nhằm tự động hóa việc tính toán, đề xuất khoảng bài tối ưu (Optimal Range) cho hành động Tố (Raise) hoặc Tất tay (All-in) trong trò chơi Liêng dân gian Việt Nam.  
**Mục tiêu cụ thể của hệ thống:**

> * **Lượng hóa bài toán:** Xây dựng mô hình toán học giải quyết việc định giá sức mạnh bài trên không gian trạng thái gồm 22,100 tổ hợp 3 lá bài.  
> * **Tối ưu hóa thời gian phản hồi:** Thiết kế kiến trúc định hướng dữ liệu (Data-driven Architecture) với cấu trúc dữ liệu Hash Table giúp tra cứu xác suất thắng với độ phức tạp thời gian O(1).  
> * **Hỗ trợ ra quyết định thời gian thực:** Cung cấp bộ lọc khoảng bài sinh lợi (EV \> 0\) dựa trên các tham số động của ván đấu (kích thước pot, lượng tiền cược, tần suất bỏ bài của đối thủ).

## **2\. Cơ Sở Lý Thuyết & Mô Hình Kỳ Vọng Toán Học (Mathematical Modeling)**

Không gian bài Liêng sử dụng bộ bài Tây tiêu chuẩn gồm 52 lá bài. Mỗi người chơi nhận ngẫu nhiên 3 lá bài úp. Tổng số tổ hợp bài có thể xảy ra được xác định bởi tổ hợp chập 3 của 52:

C(52, 3\) \= (52\!)/(3\! × 49\!) \= 22,100 tổ hợp

Khi đứng trước quyết định tăng cược (Tố hoặc Tất tay), giá trị kỳ vọng (Expected Value \- EV) của hành động được phân rã thành hai biến cố xung khắc:

> 1. **Biến cố đối thủ Bỏ bài (Fold):** Thu lại toàn bộ số tiền hiện có trong Pot (Dead Money) mà không cần ngửa bài. Xác suất xảy ra: P(Fold).  
> 2. **Biến cố đối thủ Theo cược (Call):** Hai bên ngửa bài so điểm. Kết quả chia thành hai trường hợp: Thắng (nhận Final Pot) hoặc Thua (mất số tiền đã cược). Xác suất xảy ra: 1 \- P(Fold).

**Công thức toán học tổng quát:**

EV \= \[P(Fold) × Pot\] \+ \[1 \- P(Fold)\] × \[ (P(Win|Call) × FinalPot) \- BetSize \]

Nguyên tắc ra quyết định: Chỉ thực hiện hành động Tố/Tất tay khi và chỉ khi **EV \> 0**. Giá trị EV càng lớn, quyết định càng có lợi nhuận kỳ vọng cao về dài hạn.

## **3\. Đặc Tả Luật Chơi & Cơ Chế Xếp Hạng Bài (Hand Ranking Engine)**

Bộ so sánh giá trị bài (Hand Evaluator) xây dựng quan hệ thứ tự nghiêm ngặt (Strict Ordering) giữa các bộ bài theo phân cấp giảm dần:

| Cấp bậc | Phân loại | Định nghĩa Toán học / Thuật toán | Quy tắc Xử lý Hòa (Tie-breaker) |
| :---- | :---- | :---- | :---- |
| 1 (Cao nhất) | **Sáp** | 3 lá bài có cùng giá trị số (Rank). Ví dụ: 7♠, 7♥, 7♦ | So sánh theo thứ tự: 2 \< 3 \< 4 \< ... \< K \< A. Sáp A là lớn nhất. |
| 2 | **Liêng** | 3 lá bài có giá trị số liên tiếp. Chấp nhận chuỗi (A-2-3) đến (Q-K-A). Không bắt buộc cùng chất. | Q-K-A \> K-Q-J \> ... \> A-2-3. (Nếu bằng rank thì hòa hoặc so chất theo cấu hình). |
| 3 | **Đĩ (Liên Đồng Hoa)** | Cả 3 lá bài đều là quân hình (J, Q, K) nhưng không tạo thành Sáp hoặc Liêng. | Giá trị bằng nhau (Hòa và chia đều thưởng, hoặc xét lá bài lớn nhất). |
| 4 (Cơ bản) | **Tính Điểm** | Tổng điểm 3 lá modulo 10: Điểm \= (Σ CardValue) mod 10\. Trong đó: 2-9 bằng giá trị mặt; 10, J, Q, K \= 0 điểm; A \= 1 điểm. | Thứ tự điểm số: 9 điểm \> 8 điểm \> ... \> 0 điểm (bù). |

## **4\. Kiến Trúc Kỹ Thuật & Thiết Kế Hệ Thống (Software Architecture)**

Hệ thống được thiết kế theo nguyên lý **Separation of Concerns (Phân tách mối quan tâm)** nhằm đảm bảo tính module, khả năng mở rộng và kiểm thử độc lập:

> * **Thư mục dữ liệu (/data):** Đóng vai trò là Cơ sở dữ liệu tĩnh (Static Database), lưu trữ ma trận xác suất thắng định dạng JSON. Việc tra cứu tỷ lệ thắng từ bộ nhớ sử dụng cấu trúc Bảng băm (Hash Table) với chi phí tra cứu trung bình đạt **O(1)**.  
> * **Thuật toán tối ưu hóa không gian (Hand Isomorphism):** Trong 22,100 tổ hợp 3 lá bài, rất nhiều tay bài có giá trị tương đương (đẳng cấu \- isomorphism) về mặt điểm số khi không xét chất. Hệ thống tiến hành gom nhóm thành các dạng bài chuẩn hóa (Canonical representations) để giảm dung lượng lưu trữ từ hàng megabyte xuống còn vài trăm kilobyte.  
> * **Thư mục mã nguồn (/src):** Chứa toàn bộ logic xử lý, tính toán toán học và giao diện tương tác người dùng.

## **5\. Kế Hoạch Phân Chia Công Việc Chi Tiết (Work Breakdown Structure \- WBS)**

Dự án được phân bổ công bằng và rõ ràng cho nhóm nghiên cứu 02 sinh viên:

### **Sinh Viên Minh: Phụ trách Engine Luật Chơi, Bộ Đánh Giá & Mô Phỏng Xác Suất**

**Trách nhiệm chính:** Chuyển hóa toàn bộ luật chơi thành mã nguồn, tối ưu thuật toán so bài và sinh cơ sở dữ liệu xác suất thực nghiệm.

> * **Task A.1 — Biểu diễn dữ liệu & Engine xếp hạng (**  
>   **src/evaluator.py):**  
>   • Xây dựng đối tượng lá bài (Card) và bộ bài (Deck 52 lá).  
>   • Viết hàm phân loại bài: gán trọng số phân cấp (Sáp \= 4, Liêng \= 3, Đĩ \= 2, Điểm \= 1\) và trả về tuple so sánh nhị phân chuẩn hóa: (category\_score, sub\_score).  
> * **Task A.2 — Chuẩn hóa & Thu gọn không gian trạng thái (**  
>   **src/hands.py):**  
>   • Xây dựng thuật toán gom nhóm 22,100 tổ hợp bài thành các lớp tương đương canonical.  
> * **Task A.3 — Engine mô phỏng Monte Carlo & Xuất dữ liệu (**  
>   **src/generator.py):**  
>   • Thiết kế thuật toán mô phỏng N ván đấu đối đầu (Heads-up / Multi-way) giữa từng tay bài với khoảng bài ngẫu nhiên hoặc khoảng bài giả định của đối thủ.  
>   • Tính toán tỷ lệ thắng Win-rate và xuất kết quả chuẩn hóa vào tập tin /data/winrates.json.

### **Sinh Viên Kiệt: Phụ trách Engine Tài Chính (EV), Bộ Lọc Chiến Thuật & Giao Diện**

**Trách nhiệm chính:** Xây dựng mô hình tính toán kỳ vọng toán học, quản lý nạp dữ liệu bộ nhớ, thuật toán lọc khoảng bài và xây dựng giao diện CLI.

> * **Task B.1 — Tầng nạp dữ liệu In-Memory (**  
>   **src/db.py):**  
>   • Hiện thực hóa module đọc và parse dữ liệu từ /data/winrates.json lên Hash Table (Dictionary trong bộ nhớ RAM), đảm bảo tốc độ truy vấn O(1).  
> * **Task B.2 — Module tính toán Kỳ vọng EV (**  
>   **src/ev.py):**  
>   • Lập trình hàm calculate\_ev(...) nhận các tham số đầu vào: Win-rate, Pot, Bet Size, Fold Equity để trả về giá trị kỳ vọng chính xác.  
> * **Task B.3 — Thuật toán lọc khoảng bài & Giao diện CLI (**  
>   **src/range\_finder.py,**  
>   **src/cli.py):**  
>   • Hiện thực thuật toán duyệt toàn bộ không gian bài, lọc tập hợp thỏa mãn điều kiện EV \> 0 và sắp xếp giảm dần theo mức độ sinh lời.  
>   • Xây dựng giao diện dòng lệnh tương tác bằng thư viện argparse hoặc rich, hiển thị bảng ma trận Heatmap trực quan các tay bài nên chơi.

## **6\. Phương Pháp Kiểm Thử & Tiêu Chí Đánh Giá Nghiên Cứu (Evaluation & Testing)**

Để chứng minh tính đúng đắn trước hội đồng đánh giá và giảng viên hướng dẫn, nhóm đề ra các tiêu chí kiểm thử nghiệm ngặt:

> 1. **Kiểm thử đơn vị (Unit Testing) cho Engine so bài:** Xây dựng bộ test suite bao quát 100% các trường hợp biên nhạy cảm:  
>    • So sánh Liêng A-2-3 và Q-K-A (chuỗi quấn đầu và chuỗi lớn nhất).  
>    • So sánh giữa Đĩ và bộ bài 9 điểm (kiểm tra phân cấp ưu tiên Đĩ \> Điểm).  
>    • Xử lý trường hợp đồng điểm modulo 10 (ví dụ: 19 điểm so với 9 điểm đều tính là 9 điểm).  
> 2. **Đánh giá hội tụ xác suất (Convergence Analysis):** So sánh kết quả mô phỏng Monte Carlo tại các ngưỡng số mẫu khác nhau (N \= 10,000; 100,000; 1,000,000) với xác suất lý thuyết tính bằng giải tích tổ hợp để xác định sai số biên (ε \< 0.1%).  
> 3. **Đánh giá độ phức tạp thuật toán (Algorithmic Complexity):**  
>    • Thời gian tra cứu và tính toán khoảng bài: O(H) với H là số lượng bài canonical, thời gian thực thi \< 50ms.  
>    • Chi phí bộ nhớ: Tiết kiệm tối đa nhờ việc nạp trước dữ liệu đã tiền xử lý.

## **7\. Lộ Trình Triển Khai (Project Timeline)**

| Giai đoạn | Mục tiêu & Đầu ra chính | Người thực hiện |
| :---- | :---- | :---- |
| Giai đoạn 1 (Tuần 1\) | Thống nhất Schema dữ liệu JSON; Hiện thực hóa Hand Evaluator và EV Function độc lập | Cả nhóm (Sync protocol) |
| Giai đoạn 2 (Tuần 2\) | Chạy mô phỏng xuất dữ liệu winrates.json; Lập trình module CLI và thuật toán lọc range | Sinh viên Kiệt & Minh song song |
| Giai đoạn 3 (Tuần 2\) | Tích hợp hệ thống (Integration Testing), đo đạc hiệu năng và viết báo cáo hoàn chỉnh | Cả nhóm |

*Tuyên bố từ chối trách nhiệm (Disclaimer): Dự án được thực hiện hoàn toàn cho mục đích nghiên cứu học thuật về Khoa học máy tính, Lý thuyết trò chơi và Cấu trúc dữ liệu & Giải thuật. Nhóm tác giả kiên quyết phản đối mọi hành vi cờ bạc và cá độ dưới mọi hình thức.\**  

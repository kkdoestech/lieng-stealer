# **ĐÁNH BẠI "CHIẾU BẠC" TRONG ĐÊM CÙNG LÝ THUYẾT TRÒ CHƠI VÀ AI PAIR PROGRAMMINGg**

*Câu chuyện về một đêm mất ngủ, 22,100 thế bài Liêng, và hành trình đảo ngược một tool Texas Hold'em thành công cụ tính toán Expected Value thực thụ.*

## **Phần 1: Từ Texas Hold'em đến "Chiếu Bài" Liêng Dân Gian**

Mọi chuyện bắt đầu khi tôi lướt qua repository ganjizero/stealer trên GitHub. Đó là một công cụ mã nguồn mở nhỏ gọn nhưng cực kỳ sắc bén dành cho dân chơi No-Limit Texas Hold'em. Bài toán nó giải quyết rất thực tế: *"Khi bạn ngồi ở Blind và đối thủ ở Button nâng cược để cướp pot (Steal), bạn nên 3-bet (tố ngược) với những bài xuất phát nào để có lời dài hạn?"*  
Khoảnh khắc ấy, một suy nghĩ lóe lên trong đầu tôi: Tại sao thế giới poker phương Tây có hàng tá solver, công cụ GTO (Game Theory Optimal), ma trận range bài xịn xò, trong khi các trò chơi dân gian Việt Nam đầy tính cân não như **Liêng** hay **Ba Cây** thì phần lớn người chơi vẫn đánh hoàn toàn bằng "tâm linh" và cảm tính?  
Tôi quyết định rủ cậu bạn thân trong nhóm cùng làm một mini-project: **Liêng Stealer**. Mục tiêu là dùng AI hỗ trợ pair-programming để xây dựng một engine tính toán chiến thuật ra quyết định tối ưu cho bài Liêng từ con số 0\.

## **Phần 2: Nhìn Vào Không Gian Trạng Thái (State Space)**

Trước khi viết code, chúng tôi cùng AI phân tích không gian dữ liệu của trò chơi. Liêng sử dụng bộ bài Tây 52 lá, mỗi người được chia 3 lá bài úp.

Tổng số tổ hợp 3 lá bài \= C(52, 3\) \= (52 × 51 × 50\) / (3 × 2 × 1\) \= 22,100 tổ hợp

So với Texas Hold'em pre-flop chỉ có 1,326 tổ hợp 2 lá, Liêng có số lượng tổ hợp lớn hơn gấp gần 17 lần. Phân cấp sức mạnh bài trong Liêng được xếp theo thứ tự giảm dần:

> * **Sáp:** 3 lá cùng số (ví dụ: 7-7-7, A-A-A). Tỷ lệ xuất hiện: 52 / 22,100 ≈ 0.24%.  
> * **Liêng:** 3 lá bài liên tiếp (từ A-2-3 đến Q-K-A). Tỷ lệ xuất hiện: ≈ 3.26%.  
> * **Đĩ (Liên Đồng Hoa):** 3 lá đầu người (J, Q, K) bất kỳ không tạo thành Sáp hoặc Liêng.  
> * **Tính Điểm:** Tổng giá trị các lá chia dư cho 10 (modulo 10), từ 0 điểm (bù) đến 9 điểm.

## **Phần 3: Thất Bại Đầu Tiên – Cái Bẫy "Bài Cao Thì Tố"**

Ý tưởng ngây thơ ban đầu của chúng tôi là lập trình một con bot theo luật luật cứng (Rule-based): *"Cứ bài từ 8 điểm trở lên, hoặc có Đĩ/Liêng/Sáp thì Tố hoặc Tất tay; còn dưới 8 điểm thì Bỏ bài hoặc chỉ Theo nhẹ."*  
Chúng tôi chạy thử nghiệm mô phỏng 10,000 ván đối đầu với các đối thủ biết quan sát. Kết quả là một thảm họa tài chính:

> * Khi bot có bài cực mạnh (Sáp, Liêng) và Tố lớn: Đối thủ lập tức **Bỏ bài (Fold)**. Bot chỉ ăn được số tiền cược gà ít ỏi ban đầu.  
> * Khi đối thủ chấp nhận **Theo (Call)** cú Tố của bot: Hóa ra đối thủ còn cầm bài mạnh hơn (ví dụ bot cầm 9 điểm nhưng đối thủ cầm Liêng hoặc Sáp). Bot mất trọn cây cược lớn.

Đây chính là bài học kinh điển trong Lý thuyết trò chơi: **Bạn không đánh bài bằng sức mạnh tuyệt đối trên tay mình; bạn đang đánh bài dựa trên phân phối xác suất hành vi của đối thủ và Pot Odds.**

## **Phần 4: Điểm Bứt Phá – Mô Hình Hóa Bằng Expected Value (EV)**

Sau khi nhận ra sai lầm, chúng tôi cùng AI reframe lại toàn bộ bài toán. Thay vì tự hỏi *"Bài này có to không?"*, câu hỏi đúng phải là: *"Nếu tôi Tố ở đây 1,000 lần, tôi kiếm được trung bình bao nhiêu tiền mỗi lần?"*  
Chúng tôi triển khai công thức Kỳ vọng Toán học phân tách thành 2 nhánh biến cố độc lập:

EV \= \[P(Fold) × Pot\] \+ \[1 \- P(Fold)\] × \[ (P(Win|Call) × FinalPot) \- BetSize \]

| Kịch bản (Scenario) | Xác suất (Probability) | Giá trị thu về (Payoff) |
| :---- | :---- | :---- |
| Đối thủ Bỏ bài (Fold Equity) | P(Fold) | \+ Pot hiện tại (Dead money) |
| Đối thủ Theo và mình Thắng (Showdown Win) | (1 \- P(Fold)) × P(Win|Call) | \+ FinalPot \- BetSize |
| Đối thủ Theo và mình Thua (Showdown Loss) | (1 \- P(Fold)) × (1 \- P(Win|Call)) | \- BetSize |

Khi nhìn qua lăng kính EV, một hiện tượng toán học thú vị xuất hiện: **Đôi khi cầm một bài chỉ có 1 hoặc 2 điểm (rác hoàn toàn) lại có EV dương khi Tố**, miễn là tần suất đối thủ Fold đủ cao (Fold Equity lớn). Đó chính là bản chất toán học của hành vi Bluff (Cược hù dọa)\!

## **Phần 5: Tối Ưu Hóa Thuật Toán & Data Structure (DSA)**

Thách thức kỹ thuật lớn nhất khi đưa hệ thống vào thực chiến là **tốc độ phản hồi (latency)**. Một lượt tố trong game chỉ diễn ra trong 15-30 giây. Nếu mỗi lượt đều duyệt 22,100 tổ hợp để tính mô phỏng Monte Carlo, hệ thống sẽ bị nghẽn (timeout) ngay lập tức.

### **1\. Hand Isomorphism (Thu gọn đẳng cấu)**

Trong bài Liêng tiêu chuẩn (không xét chất so le), bộ bài *7 cơ \- 8 rô \- 9 bích* có giá trị tương đương hoàn hảo với *7 tép \- 8 bích \- 9 cơ*. Bằng thuật toán Isomorphism, chúng tôi gom nhóm 22,100 tổ hợp thực tế về một tập hợp Canonical nhỏ gọn hơn rất nhiều, loại bỏ toàn bộ tính toán dư thừa.

### **2\. Pre-computing & O(1) Hash Table Lookup**

Toàn bộ tỷ lệ thắng (Win rates) của từng dạng bài khi đối đầu với các loại range đối thủ khác nhau được tính toán trước (offline simulation) và lưu trữ trong thư mục /data/winrates.json. Khi chạy chương trình, file này được nạp sẵn vào RAM dưới dạng một Dictionary (Hash Table).  
Nhờ đó, mỗi thao tác tra cứu xác suất thắng chỉ tiêu tốn đúng **O(1)** về mặt thời gian, cho phép thuật toán lọc khoảng bài hoàn thành toàn bộ phép tính chỉ trong chưa đầy **15ms**.

## **Phần 6: Chia Để Trị – Làm Việc Nhóm Với AI Assistant**

Để dự án hoàn thành đúng tiến độ trong thời gian kỷ lục, hai đứa tôi chia tách nhiệm vụ rõ ràng:

> * **Người phụ trách Game Rules & Evaluator:** Xây dựng đối tượng Card, Deck, Hand Evaluator (phân loại Sáp, Liêng, Đĩ, Điểm) và chạy code Monte Carlo sinh file xác suất thắng.  
> * **Người phụ trách EV Engine & CLI:** Xây dựng module tính EV, thuật toán quét range bài có EV \> 0 và vẽ bảng heatmap trực quan trên Terminal bằng thư viện rich.

AI đóng vai trò như một Senior Pair-Programmer ngồi cạnh: gợi ý test suite cho các trường hợp biên khó nhằn (ví dụ: so sánh Liêng A-2-3 với Q-K-A, hoặc cách phân biệt Đĩ với 3 lá đầu người trùng số), sửa lỗi logic tổ hợp và tối ưu hóa code Python.

## **Những Bài Học Đắt Giá**

> 1. **Đừng để bị đánh lừa bởi Win Rate:** Cầm bài có 80% tỷ lệ thắng không đồng nghĩa với việc bạn sẽ có lời nếu pot quá nhỏ so với số tiền bạn phải bỏ ra để theo cược. Expected Value mới là thước đo duy nhất phản ánh sự thật về mặt tài chính.  
> 2. **Reframe bài toán luôn quan trọng hơn gõ code:** Chúng tôi đã mất gần một buổi tối loay hoay với các luật if-else vô nghĩa trước khi nhận ra cốt lõi của vấn đề nằm ở công thức xác suất kỳ vọng và mô hình hành vi của đối thủ.  
> 3. **Lợi ích của AI Pair Programming:** Thay vì mất hàng tuần tra cứu cú pháp và debug các lỗi cơ bản, việc có một AI đồng hành giúp nhóm sinh viên tập trung 100% trí lực vào tư duy kiến trúc hệ thống, giải thuật và tối ưu hóa toán học.

*\*Tuyên bố từ chối trách nhiệm (Disclaimer): Dự án được thực hiện hoàn toàn cho mục đích nghiên cứu học thuật về Khoa học máy tính, Lý thuyết trò chơi và Cấu trúc dữ liệu & Giải thuật. Nhóm tác giả kiên quyết phản đối mọi hành vi cờ bạc và cá độ dưới mọi hình thức.\**
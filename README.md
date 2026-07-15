# Chat P2P – Ứng dụng nhắn tin ngang hàng bằng Python

Hệ thống sử dụng một Bootstrap Server để đăng ký, khám phá và theo dõi trạng thái các peer; nội dung chat và dữ liệu file được truyền trực tiếp giữa các peer qua TCP.

Phiên bản hiện tại có giao diện desktop bằng **PySide6**, nhắn tin riêng, chat nhóm, broadcast, lưu tin nhắn khi peer offline, mã hóa **AES-256-GCM**, chia sẻ file theo yêu cầu tải và mô phỏng churn.

## Tính năng chính

- Đăng ký peer với Bootstrap Server và khám phá các peer đang hoạt động.
- Hiển thị trạng thái online/offline theo thời gian thực.
- Nhắn tin trực tiếp giữa hai peer.
- Gửi thông báo broadcast tới các peer đang ơnline.
- Tạo nhóm và gửi tin nhắn nhóm.
- Store-and-forward: lưu tin nhắn điều khiển khi người nhận offline và chuyển tiếp khi họ online lại.
- Mã hóa nội dung tin nhắn bằng AES-256-GCM.
- Chia sẻ file trong hội thoại riêng và hội thoại nhóm.
- Người nhận chủ động bấm **Tải xuống**; file không tự động tải về máy.
- Truyền dữ liệu file trực tiếp từ peer sở hữu file tới peer tải file.
- Mã hóa từng chunk file và kiểm tra SHA-256 sau khi tải xong.
- Mô phỏng churn bằng cách cho peer luân phiên rời mạng và tham gia lại.
- Giao diện nhập thông tin kết nối trước khi mở cửa sổ chat.
- Hỗ trợ cả giao diện GUI và CLI.

## Những thay đổi nổi bật trong phiên bản mới

### 1. Giao diện khởi động

Khi chạy `run_peer_gui.py`, ứng dụng mở một cửa sổ để nhập:

- Tên người dùng.
- Cổng lắng nghe của peer.
- Địa chỉ Bootstrap Server.
- Cổng Bootstrap Server.
- Khóa mã hóa dùng chung.

Ứng dụng kiểm tra dữ liệu đầu vào trước khi tạo peer. Tên người dùng chỉ nên gồm chữ, số, dấu gạch dưới hoặc dấu gạch ngang; cổng peer phải nằm trong khoảng `1024–65535`.

Có thể bỏ qua cửa sổ này bằng tùy chọn `--no-launcher` khi đã truyền đủ tham số dòng lệnh.

### 2. Chia sẻ file theo yêu cầu tải

Luồng truyền file đã được thay đổi:

1. Người gửi chọn file trong hội thoại.
2. Ứng dụng tính SHA-256 và gửi metadata của file vào cuộc trò chuyện.
3. File xuất hiện dưới dạng thẻ chia sẻ.
4. Dữ liệu file chưa được truyền ở bước này.
5. Người nhận bấm **Tải xuống** khi muốn lưu file.
6. Người nhận chọn vị trí lưu.
7. Ứng dụng thiết lập kết nối TCP trực tiếp và truyền file đã mã hóa.

Không còn hộp thoại bắt buộc người nhận phải xác nhận và tải file ngay khi nhận thông báo.

### 3. Gửi file trong nhóm

File có thể được chia sẻ trong cả:

- Hội thoại trực tiếp.
- Hội thoại nhóm.

Khi chia sẻ trong nhóm, mỗi thành viên nhận cùng metadata file và có thể tải độc lập vào thời điểm phù hợp. Mỗi lượt tải tạo một phiên truyền riêng giữa thành viên đó và peer đã chia sẻ file.

### 4. Mô phỏng churn

Ứng dụng có hộp thoại **Mô phỏng churn** với các tham số:

- Thời gian online.
- Thời gian offline.
- Số vòng lặp.
- Jitter ngẫu nhiên.

Trong mỗi vòng, peer thực hiện quy trình:

```text
Online → UNREGISTER → đóng TCP server → Offline
       → mở lại TCP server → REGISTER → Online
```

Peer vẫn giữ cửa sổ ứng dụng trong khi offline. Khi kết nối lại, peer tiếp tục đồng bộ danh sách thành viên và nhận dữ liệu đang chờ.

## Kiến trúc hệ thống

```text
┌───────────────────────────────────────────────────────────────┐
│                      BOOTSTRAP SERVER                         │
│  • Đăng ký và hủy đăng ký peer                               │
│  • Cung cấp danh sách peer                                   │
│  • Heartbeat và phát hiện peer mất kết nối                   │
│  • Phát sự kiện PEER_JOINED / PEER_LEFT                      │
│  • Lưu thông điệp chờ cho peer offline                       │
└──────────────────────────┬────────────────────────────────────┘
                           │ TCP
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │ Alice   │◄─►│ Bob     │◄─►│ Charlie │
        │ :9001   │   │ :9002   │   │ :9003   │
        └─────────┘   └─────────┘   └─────────┘
             Chat và dữ liệu file truyền giữa các peer
```

Bootstrap Server không truyền thay dữ liệu file và không giải mã nội dung chat. Server chủ yếu giữ vai trò tracker, quản lý trạng thái và hỗ trợ store-and-forward cho các thông điệp điều khiển.

## Công nghệ sử dụng

- Python 3.10 trở lên.
- TCP Socket và đa luồng.
- JSON UTF-8 với length-prefix framing.
- PySide6 cho giao diện desktop.
- `cryptography` cho AES-256-GCM và PBKDF2-HMAC-SHA256.
- SHA-256 để kiểm tra tính toàn vẹn của file.

## Cấu trúc thư mục

```text
Chat-P2P/
├── bootstrap/
│   └── server.py                   # Bootstrap/Tracker Server
├── common/
│   ├── protocol.py                 # Giao thức và framing thông điệp
│   └── utils.py                    # Các hàm tiện ích
├── peer/
│   ├── file_transfer/
│   │   └── manager.py              # Chia sẻ và tải file theo yêu cầu
│   ├── gui/
│   │   ├── widgets/
│   │   │   ├── conversation_item.py
│   │   │   ├── file_transfer_card.py
│   │   │   └── message_bubble.py
│   │   ├── bridge.py               # Qt signal giữa backend và GUI
│   │   ├── churn_dialog.py         # Hộp thoại mô phỏng churn
│   │   ├── dialogs.py              # Các hộp thoại ứng dụng
│   │   ├── group_service.py        # Hỗ trợ dữ liệu nhóm cho GUI
│   │   ├── launch_dialog.py        # Màn hình nhập thông tin kết nối
│   │   ├── main_window.py          # Cửa sổ chat chính
│   │   ├── models.py               # Model hội thoại và tin nhắn
│   │   └── styles.py               # QSS giao diện
│   ├── churn.py                    # Bộ điều khiển churn
│   ├── cli.py                      # Giao diện dòng lệnh
│   ├── client.py                   # Kết nối Bootstrap và gửi tới peer
│   ├── crypto.py                   # Mã hóa AES-256-GCM
│   ├── node.py                     # Điều phối vòng đời Peer Node
│   ├── peer_manager.py             # Quản lý peer và nhóm
│   └── server.py                   # TCP server của peer
├── config.py                       # Cấu hình mặc định
├── requirements-gui.txt            # Thư viện cần thiết
├── run_bootstrap.py                # Chạy Bootstrap Server
├── run_peer.py                     # Chạy peer dạng CLI
├── run_peer_gui.py                 # Chạy peer dạng GUI
├── start_chat_gui.bat              # Khởi động GUI nhanh trên Windows
└── test_system.py                  # Kiểm thử nền tảng hệ thống
```

## Cài đặt

### 1. Tải mã nguồn

```bash
git clone --branch dev/hung --single-branch https://github.com/lequangduccode/Chat-P2P.git
cd Chat-P2P
```

Hoặc tải file ZIP và giải nén.

### 2. Tạo môi trường ảo

#### Windows PowerShell

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

#### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Cài thư viện

```bash
python -m pip install --upgrade pip
pip install -r requirements-gui.txt
```

Các thư viện chính:

```text
PySide6>=6.7,<7
cryptography>=42,<46
```

## Chạy ứng dụng trên một máy

Mở một terminal cho Bootstrap Server và một terminal riêng cho mỗi peer.

### Terminal 1 – Bootstrap Server

```bash
python run_bootstrap.py
```

Mặc định server chạy tại:

```text
127.0.0.1:9000
```

### Terminal 2 – Peer thứ nhất

```bash
python run_peer_gui.py
```

Nhập ví dụ:

```text
Tên người dùng: Alice
Cổng peer: 9001
Bootstrap host: 127.0.0.1
Bootstrap port: 9000
Khóa mã hóa: DoAn-P2P-2026-Secret
```

### Terminal 3 – Peer thứ hai

```bash
python run_peer_gui.py
```

Nhập tên `Bob`, cổng `9002` và cùng khóa mã hóa với Alice.

Mỗi peer chạy trên cùng một máy phải dùng một cổng khác nhau.

## Chạy GUI hoàn toàn bằng tham số dòng lệnh

```powershell
python run_peer_gui.py --no-launcher `
  --username Alice `
  --port 9001 `
  --bootstrap-host 127.0.0.1 `
  --bootstrap-port 9000 `
  --encryption-key "DoAn-P2P-2026-Secret"
```

Viết trên một dòng:

```powershell
python run_peer_gui.py --no-launcher --username Alice --port 9001 --bootstrap-host 127.0.0.1 --bootstrap-port 9000 --encryption-key "DoAn-P2P-2026-Secret"
```

Khi dùng `--no-launcher`, bắt buộc phải có `username`, `port` và khóa mã hóa.

## Khóa mã hóa

Tất cả peer muốn trao đổi dữ liệu phải sử dụng cùng một khóa.

Có thể truyền trực tiếp:

```powershell
python run_peer_gui.py --no-launcher --username Alice --port 9001 --encryption-key "DoAn-P2P-2026-Secret"
```

Hoặc đặt biến môi trường trong PowerShell:

```powershell
$env:P2P_ENCRYPTION_KEY = "DoAn-P2P-2026-Secret"
python run_peer_gui.py
```

Lưu lâu dài trên Windows:

```powershell
setx P2P_ENCRYPTION_KEY "DoAn-P2P-2026-Secret"
```

Sau khi dùng `setx`, cần mở cửa sổ terminal mới.

Không nên commit khóa thật lên GitHub hoặc ghi trực tiếp khóa dùng trong triển khai vào source code.

## Sử dụng giao diện

### Nhắn tin riêng

1. Chọn một peer trong danh sách hội thoại.
2. Nhập nội dung.
3. Nhấn **Gửi** hoặc Enter.

### Broadcast

Chức năng broadcast gửi nội dung tới tất cả peer đang online. Peer offline không nhận broadcast tại thời điểm gửi.

### Tạo nhóm

1. Nhấn nút tạo nhóm.
2. Nhập tên nhóm.
3. Chọn các thành viên.
4. Xác nhận tạo nhóm.
5. Chọn nhóm trong danh sách để nhắn tin hoặc chia sẻ file.

### Chia sẻ file trong chat riêng

1. Mở hội thoại với peer cần chia sẻ.
2. Nhấn nút đính kèm.
3. Chọn file.
4. Ứng dụng tính SHA-256 và đăng thẻ file vào hội thoại.
5. Người nhận bấm **Tải xuống** khi muốn tải.
6. Người nhận chọn thư mục và tên file đích.

### Chia sẻ file trong nhóm

1. Mở hội thoại nhóm.
2. Nhấn nút đính kèm.
3. Chọn file.
4. Metadata file được gửi tới các thành viên nhóm.
5. Mỗi thành viên tự bấm **Tải xuống** và tải file trực tiếp từ người gửi.

### Trạng thái thẻ file

Một thẻ file có thể hiển thị các trạng thái:

- `preparing`: đang tính SHA-256.
- `shared`: đã chia sẻ metadata.
- `available`: sẵn sàng tải xuống.
- `connecting`: đang yêu cầu tải.
- `waiting`: chờ kết nối truyền dữ liệu.
- `transferring`: đang tải file.
- `completed`: đã tải xong.
- `failed`: tải thất bại.
- `cancelled`: đã hủy tải.

### Điều kiện để tải file

- File phải còn tồn tại tại đường dẫn gốc trên máy người gửi.
- Người gửi phải đang chạy ứng dụng và online khi thành viên bấm tải.
- Hai peer phải kết nối được trực tiếp tới cổng TCP của nhau.
- Tất cả peer phải dùng cùng khóa mã hóa.
- File không được rỗng và không vượt quá 100 MB.

Việc gửi metadata có thể được lưu chờ khi thành viên offline, nhưng dữ liệu file chỉ truyền khi người gửi và người tải cùng online.

## Mô phỏng churn

### Cách sử dụng

1. Mở ứng dụng GUI.
2. Nhấn **Mô phỏng churn**.
3. Nhập thời gian online, thời gian offline và số vòng.
4. Bật jitter nếu muốn thời gian dao động ngẫu nhiên.
5. Nhấn bắt đầu.

Cấu hình mặc định trong code:

```text
Online: 10 giây
Offline: 5 giây
Số vòng: 3
Jitter: 0 giây
```

### Hành vi khi peer offline do churn

- Gửi `UNREGISTER` tới Bootstrap Server.
- Dừng nhận kết nối tại TCP server của peer.
- Peer khác nhận trạng thái rời mạng.
- Không thể gửi tin hoặc tải file trực tiếp trong giai đoạn offline.
- Các phiên truyền file đang hoạt động có thể bị hủy.

### Hành vi khi peer online lại

- Mở lại TCP server trên cùng cổng.
- Đăng ký lại với cùng `peer_id` và username.
- Đồng bộ lại danh sách peer.
- Tiếp tục nhận các thông điệp đang chờ.

Khi dừng mô phỏng, controller cố gắng đưa peer trở lại trạng thái online.

## Chạy trên nhiều máy trong mạng LAN

### Máy chạy Bootstrap Server

```bash
python run_bootstrap.py --host 0.0.0.0 --port 9000
```

Giả sử IPv4 của máy Bootstrap là `192.168.1.100`.

### Máy chạy peer

```powershell
python run_peer_gui.py --no-launcher --username Alice --port 9001 --bootstrap-host 192.168.1.100 --bootstrap-port 9000 --encryption-key "DoAn-P2P-2026-Secret"
```

Các máy cần:

- Ở cùng mạng LAN hoặc định tuyến được tới nhau.
- Cho phép cổng Bootstrap qua firewall.
- Cho phép cổng lắng nghe của từng peer qua firewall.
- Không dùng trùng username trong cùng hệ thống.

## Giao diện dòng lệnh

Chạy peer CLI:

```bash
python run_peer.py --username Alice --port 9001
python run_peer.py --username Bob --port 9002
```

Bật log chi tiết cho CLI:

```bash
python run_peer.py --username Alice --port 9001 --debug
```

Các lệnh hiện có:

```text
list                              Xem peer đang online
msg Bob Xin chào!                 Gửi tin nhắn trực tiếp
broadcast Thông báo chung         Gửi tới các peer online
groups                            Xem danh sách nhóm
group create Team Bob Charlie     Tạo nhóm
group msg Team Họp lúc 15h        Gửi tin nhắn nhóm
help                              Hiển thị trợ giúp
quit                              Thoát
```

Các chức năng GUI như chia sẻ file và mô phỏng churn chưa được cung cấp thành lệnh CLI tương tác.

## Giao thức truyền thông

Thông điệp điều khiển được đóng khung:

```text
[4-byte big-endian length][N-byte JSON UTF-8]
```

Các nhóm thông điệp chính:

| Nhóm | Loại thông điệp |
|---|---|
| Bootstrap | `REGISTER`, `REGISTER_OK`, `UNREGISTER`, `HEARTBEAT`, `GET_PEERS`, `PEER_LIST` |
| Trạng thái | `PEER_JOINED`, `PEER_LEFT` |
| Chat | `DIRECT_MSG`, `BROADCAST_MSG`, `GROUP_MSG`, `GROUP_INVITE`, `ACK` |
| File | `FILE_SHARE`, `FILE_DOWNLOAD_REQUEST`, `FILE_CANCEL`, `FILE_STREAM_BEGIN`, `FILE_STREAM_RESULT` |

### Luồng giao thức file

```text
Người gửi                                  Người nhận
    │                                           │
    │──── FILE_SHARE (metadata) ───────────────►│
    │                                           │
    │                         Người dùng bấm tải │
    │◄── FILE_DOWNLOAD_REQUEST + host/port ─────│
    │                                           │
    │──── FILE_STREAM_BEGIN ───────────────────►│
    │──── encrypted chunk 0 ───────────────────►│
    │──── encrypted chunk 1 ───────────────────►│
    │──── ... ─────────────────────────────────►│
    │──── zero-length marker ──────────────────►│
    │◄── FILE_STREAM_RESULT ────────────────────│
```

Mỗi chunk có kích thước tối đa khoảng `256 KB` trước khi mã hóa. Thời gian timeout cho một phiên truyền file là `60 giây`.

## Cơ chế bảo mật

- Passphrase được dẫn xuất thành khóa 256-bit bằng PBKDF2-HMAC-SHA256.
- Nội dung chat được mã hóa bằng AES-256-GCM.
- Từng chunk file được mã hóa độc lập bằng AES-256-GCM.
- Associated Data liên kết bản mã với phiên chia sẻ, yêu cầu tải và chỉ số chunk.
- SHA-256 được tính trước khi chia sẻ và đối chiếu sau khi tải.
- File tạm dùng hậu tố `.part` và chỉ được đổi sang tên chính thức sau khi kiểm tra thành công.

Đây là mô hình khóa dùng chung phục vụ đồ án. Hệ thống chưa triển khai ECDH/RSA để trao đổi khóa, chứng thư số, forward secrecy hoặc xác thực danh tính mạnh.

## Kiểm thử

Chạy bộ kiểm thử hiện có:

```bash
python test_system.py
```

Bộ kiểm thử hiện tập trung vào:

- Encode/decode giao thức.
- Đăng ký Bootstrap Server.
- Khám phá peer.
- Chat trực tiếp.
- Chat nhóm.
- Store-and-forward.
- Retry khi kết nối thất bại.

Các luồng GUI, tải file theo yêu cầu, gửi file nhóm và churn nên được kiểm thử tích hợp riêng khi hoàn thiện sản phẩm.

## Kịch bản kiểm thử đề xuất

### Kiểm thử chia sẻ file trực tiếp

1. Khởi động Alice và Bob.
2. Alice chia sẻ file cho Bob.
3. Xác nhận file chưa tự động xuất hiện trong thư mục Downloads của Bob.
4. Bob bấm **Tải xuống**.
5. Chọn vị trí lưu.
6. So sánh SHA-256 hoặc nội dung hai file.

### Kiểm thử file nhóm

1. Tạo nhóm gồm Alice, Bob và Charlie.
2. Alice chia sẻ một file trong nhóm.
3. Bob tải file.
4. Charlie chưa tải và vẫn chỉ nhìn thấy thẻ file.
5. Charlie tải file ở thời điểm khác.
6. Kiểm tra cả hai bản tải đều khớp file gốc.

### Kiểm thử peer gửi offline

1. Alice chia sẻ file vào nhóm.
2. Alice chuyển offline hoặc đóng ứng dụng.
3. Bob bấm tải và xác nhận ứng dụng báo người gửi offline.
4. Alice online lại.
5. Bob bấm tải lại và xác nhận tải thành công.

### Kiểm thử churn

1. Chạy ít nhất hai peer.
2. Bật churn trên một peer với chu kỳ ngắn.
3. Quan sát peer còn lại nhận `PEER_LEFT` và `PEER_JOINED`.
4. Gửi tin trong lúc peer churn đang offline.
5. Kiểm tra dữ liệu chờ được chuyển khi peer online lại.

## Xử lý lỗi thường gặp

### Không kết nối được Bootstrap Server

- Kiểm tra `run_bootstrap.py` đang chạy.
- Kiểm tra đúng host và port.
- Kiểm tra firewall hoặc antivirus.
- Kiểm tra cổng Bootstrap chưa bị ứng dụng khác sử dụng.

### Không mở được peer

- Không dùng trùng username.
- Không dùng trùng cổng peer trên cùng máy.
- Cổng peer phải từ `1024–65535`.
- Kiểm tra cổng chưa bị tiến trình khác chiếm.

### Hai peer không nhìn thấy nhau

- Kiểm tra cả hai đã đăng ký thành công.
- Kiểm tra địa chỉ IP mà peer công bố có thể truy cập được.
- Chờ chu kỳ làm mới danh sách hoặc khởi động lại peer.
- Trong LAN, kiểm tra ping và firewall giữa các máy.

### Không giải mã được tin nhắn hoặc file

- Bảo đảm tất cả peer dùng cùng khóa.
- Không thay khóa khi ứng dụng đang chạy.
- Khởi động lại peer sau khi đổi biến môi trường.

### Không chia sẻ được file

- File phải tồn tại và có quyền đọc.
- File không được rỗng.
- File không vượt quá 100 MB.
- Hội thoại hoặc nhóm phải tồn tại.

### Không tải được file

- Người gửi phải online.
- File gốc không được di chuyển, đổi tên hoặc xóa sau khi chia sẻ.
- Cổng peer nhận phải cho phép kết nối vào.
- Thư mục đích phải có quyền ghi.
- Thử tải lại nếu kết nối bị gián đoạn.

### File bị trùng tên

Nếu đường dẫn đích đã tồn tại tại thời điểm hoàn tất, ứng dụng tự tạo tên mới theo dạng:

```text
ten-file (1).ext
ten-file (2).ext
```

## Giới hạn hiện tại

- Bootstrap Server vẫn là điểm trung tâm cho discovery và store-and-forward.
- File chỉ tải được khi peer sở hữu file đang online.
- Chưa hỗ trợ resume một file đang tải dở.
- Chưa hỗ trợ NAT traversal qua Internet công cộng.
- Lịch sử GUI chủ yếu được giữ trong phiên chạy hiện tại.
- Nhóm chưa có cơ chế đồng thuận hoặc quản trị thành viên nâng cao.
- Một khóa dùng chung được sử dụng cho toàn mạng thử nghiệm.

## Hướng phát triển

- Trao đổi khóa bằng ECDH và xác thực peer.
- Lưu lịch sử hội thoại bằng SQLite hoặc cơ sở dữ liệu phân tán.
- Resume và retry truyền file theo chunk.
- Lưu metadata file bền vững qua nhiều lần khởi động.
- Hỗ trợ NAT traversal bằng STUN/TURN hoặc relay.
- Phân quyền quản trị nhóm.
- Kiểm thử tự động cho file nhóm, churn và GUI.
- Đóng gói ứng dụng Windows bằng PyInstaller.
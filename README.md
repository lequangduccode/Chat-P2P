# Chat P2P – Ứng dụng nhắn tin ngang hàng bằng Python

Ứng dụng chat ngang hàng (Peer-to-Peer) được xây dựng cho đồ án môn **Các hệ thống phân tán**. Bootstrap Server chỉ thực hiện đăng ký, khám phá và theo dõi trạng thái peer; nội dung chat và file được truyền trực tiếp giữa các peer qua TCP.

Phiên bản hiện tại cung cấp giao diện **PySide6**, nhắn tin riêng, chat nhóm, lưu tin nhắn khi người nhận offline, mã hóa **AES-256-GCM** và truyền file trực tiếp có mã hóa.

## Tính năng chính

- Đăng ký peer và khám phá người dùng đang trực tuyến.
- Hiển thị trạng thái online/offline theo thời gian thực.
- Nhắn tin trực tiếp giữa hai peer.
- Tạo nhóm và gửi tin nhắn nhóm.
- Store-and-forward: lưu tin nhắn khi người nhận offline và chuyển tiếp khi họ kết nối lại.
- Mã hóa nội dung tin nhắn bằng AES-256-GCM.
- Truyền file trực tiếp giữa hai peer, giới hạn 100 MB/file.
- Mã hóa từng khối dữ liệu file và kiểm tra SHA-256 sau khi nhận.
- Giao diện desktop bằng PySide6 và giao diện dòng lệnh CLI.
- Heartbeat, timeout và xử lý peer ngắt kết nối.

## Kiến trúc hệ thống

```text
┌───────────────────────────────────────────────────────────────┐
│                      BOOTSTRAP SERVER                         │
│  • Đăng ký và quản lý danh sách peer                         │
│  • Heartbeat và phát hiện peer mất kết nối                   │
│  • Phát sự kiện PEER_JOINED / PEER_LEFT                      │
└──────────────────────────┬────────────────────────────────────┘
                           │ TCP
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │ Alice   │◄─►│ Bob     │◄─►│ Charlie │
        │ :9001   │   │ :9002   │   │ :9003   │
        └─────────┘   └─────────┘   └─────────┘
             Chat và file truyền trực tiếp giữa các peer
```

Bootstrap Server không giải mã nội dung chat hoặc nội dung file. Tuy nhiên, các metadata cần thiết cho việc định tuyến như loại thông điệp, tên người gửi, mã peer, mã nhóm và thời gian vẫn tồn tại ở dạng rõ.

## Công nghệ sử dụng

- Python 3.10 trở lên.
- TCP Socket và đa luồng.
- JSON message protocol với length-prefix framing.
- PySide6 cho giao diện desktop.
- `cryptography` cho AES-256-GCM và PBKDF2-HMAC-SHA256.
- SHA-256 để kiểm tra tính toàn vẹn của file.

## Cấu trúc thư mục

```text
Chat-P2P/
├── bootstrap/
│   └── server.py                 # Bootstrap/Tracker Server
├── common/
│   ├── protocol.py               # Giao thức, encode/decode thông điệp
│   └── utils.py                  # Hàm tiện ích
├── peer/
│   ├── file_transfer/
│   │   └── manager.py            # Quản lý truyền file mã hóa
│   ├── gui/
│   │   ├── widgets/              # Message bubble, file card, conversation item
│   │   ├── bridge.py             # Cầu nối backend và Qt signal
│   │   ├── dialogs.py            # Hộp thoại nhóm và nhận file
│   │   ├── main_window.py        # Cửa sổ chính
│   │   ├── models.py             # Model dữ liệu GUI
│   │   └── styles.py             # Giao diện QSS
│   ├── cli.py                    # Giao diện dòng lệnh
│   ├── client.py                 # Kết nối bootstrap và gửi tới peer
│   ├── crypto.py                 # Mã hóa AES-256-GCM
│   ├── node.py                   # Điều phối Peer Node
│   ├── peer_manager.py           # Quản lý peer và nhóm
│   └── server.py                 # TCP server của peer
├── config.py                     # Cấu hình mặc định
├── requirements-gui.txt          # Thư viện cho GUI và mã hóa
├── run_bootstrap.py              # Chạy Bootstrap Server
├── run_peer.py                   # Chạy peer dạng CLI
├── run_peer_gui.py               # Chạy peer dạng GUI
└── test_system.py                # Kiểm thử hệ thống
```

## Cài đặt

### 1. Tải mã nguồn

Clone đúng nhánh `dev/hung`:

```bash
git clone --branch dev/hung --single-branch https://github.com/lequangduccode/Chat-P2P.git
cd Chat-P2P
```

Hoặc tải file ZIP của project và giải nén.

### 2. Tạo môi trường ảo

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn script trong phiên terminal hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Dòng `(.venv)` xuất hiện trước dấu nhắc PowerShell chỉ cho biết môi trường ảo đang được kích hoạt, không phải lỗi.

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

## Chạy ứng dụng trên một máy

Cần mở ít nhất ba terminal: một terminal chạy Bootstrap Server và hai terminal chạy hai peer khác nhau.

### Terminal 1 – Bootstrap Server

```bash
python run_bootstrap.py
```

Mặc định Bootstrap Server chạy tại `127.0.0.1:9000`.

### Terminal 2 – Alice

```bash
python run_peer_gui.py --username Alice --port 9001
```

### Terminal 3 – Bob

```bash
python run_peer_gui.py --username Bob --port 9002
```

Có thể mở thêm peer:

```bash
python run_peer_gui.py --username Charlie --port 9003
```

Mỗi peer trên cùng một máy phải sử dụng một cổng khác nhau.

## Cấu hình khóa mã hóa

Ứng dụng có khóa mặc định `p2p-chat-demo-2026` để thuận tiện khi chạy thử. Trong triển khai thực tế, nên đặt một khóa riêng có ít nhất 8 ký tự và bảo đảm tất cả peer sử dụng cùng một khóa.

### Cách 1 – Truyền khóa trực tiếp khi chạy

```powershell
python run_peer_gui.py --username Alice --port 9001 --encryption-key "DoAn-P2P-2026-Secret"
python run_peer_gui.py --username Bob --port 9002 --encryption-key "DoAn-P2P-2026-Secret"
```

### Cách 2 – Đặt biến môi trường cho terminal hiện tại

```powershell
$env:P2P_ENCRYPTION_KEY = "DoAn-P2P-2026-Secret"
python run_peer_gui.py --username Alice --port 9001
```

Biến trên chỉ tồn tại trong cửa sổ PowerShell hiện tại. Khi mở terminal mới, cần đặt lại.

### Cách 3 – Lưu biến môi trường lâu dài trên Windows

```powershell
setx P2P_ENCRYPTION_KEY "DoAn-P2P-2026-Secret"
```

Sau khi chạy `setx`, đóng và mở lại PowerShell. Không nên commit khóa thật vào GitHub hoặc ghi trực tiếp vào source code.

Khi các peer dùng cùng khóa, giao diện sẽ hiển thị cùng một **Key ID**. Nếu khóa không khớp, peer nhận sẽ không thể xác thực và giải mã tin nhắn hoặc file.

## Sử dụng giao diện

### Nhắn tin riêng

1. Chọn một peer trong danh sách bên trái.
2. Nhập nội dung vào ô soạn tin.
3. Nhấn **Gửi** hoặc phím Enter.

### Tạo và chat nhóm

1. Nhấn **Tạo nhóm**.
2. Nhập tên nhóm và chọn thành viên.
3. Chọn nhóm trong danh sách hội thoại rồi gửi tin nhắn.

### Gửi file

1. Chọn một peer đang online.
2. Nhấn nút đính kèm cạnh ô nhập tin nhắn.
3. Chọn file cần gửi.
4. Người nhận chọn vị trí lưu và chấp nhận đề nghị.
5. Theo dõi tiến trình ngay trong thẻ truyền file.

Lưu ý:

- Chỉ hỗ trợ gửi file trực tiếp cho một peer đang online.
- Kích thước tối đa là 100 MB.
- File được chia thành các chunk 256 KB và mỗi chunk được mã hóa AES-256-GCM.
- Sau khi nhận xong, ứng dụng kiểm tra kích thước và SHA-256 của file.
- Không đóng ứng dụng hoặc ngắt mạng khi đang truyền file.

## Chạy trên nhiều máy trong cùng mạng LAN

### Máy chạy Bootstrap Server

```bash
python run_bootstrap.py --host 0.0.0.0 --port 9000
```

Xác định địa chỉ IPv4 của máy này, ví dụ `192.168.1.100`, và cho phép cổng `9000` qua Windows Firewall.

### Máy chạy peer

```bash
python run_peer_gui.py \
  --username Alice \
  --port 9001 \
  --bootstrap-host 192.168.1.100 \
  --bootstrap-port 9000
```

Trên Windows PowerShell có thể viết trên một dòng:

```powershell
python run_peer_gui.py --username Alice --port 9001 --bootstrap-host 192.168.1.100 --bootstrap-port 9000
```

Mỗi máy peer cũng cần cho phép cổng peer tương ứng qua firewall để nhận tin nhắn và kết nối truyền file trực tiếp.

## Giao diện dòng lệnh

Khởi động các peer dạng CLI:

```bash
python run_peer.py --username Alice --port 9001
python run_peer.py --username Bob --port 9002
```

Một số lệnh cơ bản:

```text
list                            Xem danh sách peer
msg Bob Xin chào!               Gửi tin nhắn riêng
broadcast Thông báo chung       Gửi tới các peer online
group create Team Bob Charlie   Tạo nhóm
group msg Team Họp lúc 15h      Gửi tin nhắn nhóm
groups                          Xem danh sách nhóm
help                            Xem trợ giúp
quit                            Thoát
```

GUI là chế độ được khuyến nghị cho chức năng truyền file.

## Giao thức truyền thông

Thông điệp điều khiển sử dụng JSON UTF-8 với 4 byte độ dài ở đầu:

```text
[4-byte big-endian length][N-byte JSON payload]
```

Các nhóm thông điệp chính:

| Nhóm | Loại thông điệp |
|---|---|
| Bootstrap | `REGISTER`, `REGISTER_OK`, `UNREGISTER`, `HEARTBEAT`, `GET_PEERS`, `PEER_LIST` |
| Trạng thái peer | `PEER_JOINED`, `PEER_LEFT` |
| Chat | `DIRECT_MSG`, `GROUP_MSG`, `GROUP_INVITE`, `ACK` |
| Truyền file | `FILE_OFFER`, `FILE_ACCEPT`, `FILE_REJECT`, `FILE_CANCEL`, `FILE_STREAM_BEGIN`, `FILE_STREAM_RESULT` |

## Cơ chế bảo mật

- Passphrase được dẫn xuất thành khóa 256-bit bằng PBKDF2-HMAC-SHA256.
- Tin nhắn và từng chunk file sử dụng nonce ngẫu nhiên 96-bit.
- AES-GCM vừa mã hóa vừa xác thực dữ liệu.
- Associated Data ràng buộc bản mã với một số metadata định tuyến.
- Key ID là fingerprint rút gọn để đối chiếu khóa, không phải khóa bí mật.

Đây là mô hình khóa dùng chung phục vụ đồ án và mạng tin cậy. Hệ thống hiện chưa triển khai trao đổi khóa bất đối xứng, chứng thực danh tính bằng chứng thư số hoặc forward secrecy.

## Kiểm thử

Chạy bộ kiểm thử tích hợp:

```bash
python test_system.py
```

Có thể chạy ứng dụng với log chi tiết:

```bash
python run_peer_gui.py --username Alice --port 9001 --debug
```

## Xử lý lỗi thường gặp

### Không kết nối được Bootstrap Server

- Kiểm tra `run_bootstrap.py` đang chạy.
- Kiểm tra đúng IP và cổng Bootstrap.
- Kiểm tra firewall hoặc antivirus.

### Hai peer không nhìn thấy nhau

- Không dùng trùng username hoặc cổng trên cùng máy.
- Đợi chu kỳ đồng bộ danh sách peer hoặc khởi động lại peer.
- Khi chạy LAN, kiểm tra các máy cùng mạng và có thể ping lẫn nhau.

### Không giải mã được tin nhắn hoặc file

- Kiểm tra tất cả peer dùng cùng `P2P_ENCRYPTION_KEY`.
- So sánh Key ID hiển thị trên giao diện.
- Khởi động lại peer sau khi thay biến môi trường.

### Không gửi được file

- Người nhận phải đang online.
- File phải nhỏ hơn hoặc bằng 100 MB và không được rỗng.
- Kiểm tra cổng peer không bị firewall chặn.
- Bảo đảm đủ quyền đọc file nguồn và quyền ghi tại thư mục đích.

## Repository

Nhánh phát triển của phiên bản này:

```text
https://github.com/lequangduccode/Chat-P2P/tree/dev/hung
```

## Phạm vi và định hướng phát triển

Một số hướng mở rộng phù hợp:

- Trao đổi khóa bằng RSA/ECDH thay cho khóa dùng chung.
- Xác thực danh tính peer và chống giả mạo.
- Lưu lịch sử hội thoại bằng cơ sở dữ liệu.
- Resume truyền file khi mất kết nối.
- Truyền file trong nhóm.
- NAT traversal để hoạt động qua Internet.
- Đóng gói ứng dụng Windows bằng PyInstaller.

## Giấy phép

Project phục vụ mục đích học tập và nghiên cứu. Hãy bổ sung tệp `LICENSE` nếu muốn công bố với một giấy phép mã nguồn mở cụ thể.
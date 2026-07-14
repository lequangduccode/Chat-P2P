# Giao diện PySide6 cho Chat-P2P

Bộ mã này là lớp giao diện bổ sung cho repository `lequangduccode/Chat-P2P`.
Nó giữ nguyên toàn bộ lớp mạng hiện có: TCP socket, ACK, heartbeat, bootstrap discovery,
chat nhóm và store-and-forward.

## Tính năng giao diện

- Danh sách peer online/offline và tìm kiếm nhanh.
- Chat trực tiếp; peer offline vẫn nhận được tin qua cơ chế store-and-forward của backend.
- Chat nhóm, tạo nhóm và chọn thành viên.
- Broadcast tới toàn bộ peer online.
- Bong bóng tin nhắn, badge chưa đọc, trạng thái gửi/đang chờ.
- Qt Signal bảo đảm cập nhật UI an toàn khi callback đến từ thread socket.
- Làm mới danh sách tự động và thủ công.
- Tắt cửa sổ sẽ unregister peer và dừng server.

## Cách tích hợp

Sao chép toàn bộ nội dung thư mục này vào thư mục gốc của repository Chat-P2P.
Sau khi chép, cấu trúc mới sẽ có:

```text
Chat-P2P/
├── run_peer_gui.py
├── requirements-gui.txt
└── peer/
    └── gui/
        ├── bridge.py
        ├── dialogs.py
        ├── main_window.py
        ├── models.py
        ├── styles.py
        └── widgets/
```

Không xóa hoặc thay thế `peer/node.py`, `peer/client.py`, `peer/server.py`.

## Cài đặt

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements-gui.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements-gui.txt
```

## Chạy thử trên một máy

Terminal 1:

```bash
python run_bootstrap.py
```

Terminal 2:

```bash
python run_peer_gui.py -u Alice -p 9001
```

Terminal 3:

```bash
python run_peer_gui.py -u Bob -p 9002
```

Terminal 4:

```bash
python run_peer_gui.py -u Charlie -p 9003
```

## Chạy trong mạng LAN

Máy bootstrap:

```bash
python run_bootstrap.py --host 0.0.0.0 --port 9000
```

Các máy peer:

```bash
python run_peer_gui.py -u Alice -p 9001 --bootstrap-host 192.168.1.100
```

Hãy cho phép Python qua Windows Firewall và mở cổng bootstrap/peer tương ứng.

## Lưu ý tương thích

Giao diện dựa trên API đang có của repository:

- `node.send_direct(username, content)`
- `node.send_group(group_name, content)`
- `node.create_group(group_name, members)`
- `node.broadcast(content)`
- `node.manager.all_peers()`
- `node.manager.all_groups()`

`NodeBridge` nối trực tiếp vào callback của `PeerNode`; không phân tích chuỗi console để xác định tin nhắn.

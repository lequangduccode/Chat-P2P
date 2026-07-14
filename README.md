# Hệ thống Chat Ngang Hàng P2P

Đồ án môn Các Hệ Thống Phân Tán – Chủ đề 3

---

## Kiến trúc hệ thống

```
┌──────────────────────────────────────────────────────────────────┐
│                     BOOTSTRAP SERVER                             │
│   • Quản lý registry peer (peer_id → host:port:username)         │
│   • Heartbeat timeout (60s)                                      │
│   • Push PEER_JOINED / PEER_LEFT tới tất cả peer                 │
└──────────────┬───────────────────────────────────────────────────┘
               │ TCP (register / heartbeat / get_peers)
    ┌──────────┴──────────┬──────────────────┐
    ▼                     ▼                  ▼
┌────────┐          ┌────────┐          ┌────────┐
│ Peer A │◄────────►│ Peer B │◄────────►│ Peer C │
│ :9001  │          │ :9002  │          │ :9003  │
└────────┘          └────────┘          └────────┘
  TCP trực tiếp – không qua server trung tâm
```

### Các thành phần

| Module | File | Mô tả |
|--------|------|-------|
| Bootstrap Server | `bootstrap/server.py` | Tracker – quản lý danh sách peer |
| Peer Server | `peer/server.py` | Lắng nghe kết nối đến từ peer khác |
| Peer Client | `peer/client.py` | Gửi tin & giao tiếp với bootstrap |
| Peer Manager | `peer/peer_manager.py` | Bộ nhớ trong: danh sách peer, nhóm |
| Peer Node | `peer/node.py` | Điều phối trung tâm |
| CLI | `peer/cli.py` | Giao diện dòng lệnh |

---

## Giao thức tin nhắn (Message Protocol)

**Framing**: 4-byte big-endian length prefix + UTF-8 JSON payload

```
[ 4 bytes: độ dài ] [ N bytes: JSON ]
```

### Các loại tin nhắn

| Type | Chiều | Mô tả |
|------|-------|-------|
| `REGISTER` | Peer → Bootstrap | Đăng ký tham gia mạng |
| `REGISTER_OK` | Bootstrap → Peer | Xác nhận đăng ký |
| `HEARTBEAT` | Peer → Bootstrap | Báo hiệu còn sống (mỗi 15s) |
| `GET_PEERS` | Peer → Bootstrap | Lấy danh sách peer online |
| `PEER_LIST` | Bootstrap → Peer | Danh sách peer online |
| `PEER_JOINED` | Bootstrap → Peers | Push: có peer mới tham gia |
| `PEER_LEFT` | Bootstrap → Peers | Push: có peer rời mạng |
| `DIRECT_MSG` | Peer → Peer | Tin nhắn trực tiếp 1-1 |
| `GROUP_MSG` | Peer → Peers | Tin nhắn nhóm |
| `GROUP_INVITE` | Peer → Peers | Mời tham gia nhóm |
| `ACK` | Nhận → Gửi | Xác nhận nhận tin |

---

## Yêu cầu

- Python **3.10+**
- Không cần cài thêm thư viện (chỉ dùng stdlib)

---

## Cài đặt & Chạy

### 1. Khởi động Bootstrap Server

```bash
cd p2p_chat
python run_bootstrap.py
```

Tuỳ chọn:
```bash
python run_bootstrap.py --host 0.0.0.0 --port 9000
```

### 2. Mở nhiều terminal, chạy các peer

**Terminal 2:**
```bash
python run_peer.py --username Alice --port 9001
```

**Terminal 3:**
```bash
python run_peer.py --username Bob --port 9002
```

**Terminal 4:**
```bash
python run_peer.py --username Charlie --port 9003
```

### 3a. Giao diện đồ hoạ (GUI) — khuyến nghị khi demo

Thay cho CLI, có thể chạy peer bằng cửa sổ Tkinter (không cần cài thêm gì):

```bash
python run_gui.py                       # nhập tên/cổng trên màn hình đăng nhập
python run_gui.py -u Alice -p 9001      # hoặc điền sẵn bằng tham số
python run_gui.py -u Bob   -p 9002
```

Trong cửa sổ: chọn peer/nhóm ở cột trái → gõ tin nhắn → **Gửi**.
Có nút **Tạo nhóm** (chọn thành viên bằng checkbox) và **Broadcast toàn mạng**.

### 3b. Sử dụng CLI

```
>>> list                            # Xem peer đang online
>>> msg Bob Xin chào!               # Nhắn riêng cho Bob
>>> group create Team Bob Charlie   # Tạo nhóm "Team" với Bob và Charlie
>>> group msg Team Họp lúc 3h nhé   # Nhắn vào nhóm Team
>>> groups                          # Xem danh sách nhóm
>>> quit                            # Thoát
```

### 3c. Chức năng nâng cao

**🔐 Mã hoá tin nhắn** — mọi tin nhắn/​file giữa các peer được mã hoá bằng
sơ đồ *encrypt-then-MAC* (PBKDF2 + keystream HMAC-SHA256, chỉ dùng stdlib).
Các peer phải dùng chung khoá; đổi khoá bằng `--key`:
```bash
python run_gui.py -u Alice -p 9001 --key bem-mat-nhom7
python run_peer.py -u Bob -p 9002 --key bem-mat-nhom7
```
Peer dùng sai khoá sẽ nhận `⚠[không giải mã được]`. GUI hiển thị `🔒 Mã hoá: BẬT`.

**📎 File transfer** — trong GUI, chọn 1 peer → nút **📎 File** → chọn file
(≤ 5 MB). File được mã hoá, gửi trực tiếp peer→peer, lưu vào `downloads/`.

**🔄 Mô phỏng churn** — tạo các bot tự vào/ra mạng liên tục để kiểm thử
tính chịu lỗi (chạy song song với các peer GUI thật):
```bash
python churn_sim.py --peers 3 --duration 60
python churn_sim.py --peers 5 --duration 120 --bootstrap-host 172.17.9.8
```

### 4. Chạy trên nhiều máy tính

Trên máy chủ (bootstrap), mở port 9000:
```bash
python run_bootstrap.py --host 0.0.0.0
```

Trên máy client, chỉ định IP của bootstrap:
```bash
python run_peer.py -u Alice -p 9001 --bootstrap-host 192.168.1.100
```

---

## Tính năng đã triển khai

| Yêu cầu | Trạng thái |
|---------|-----------|
| Đăng ký / rời mạng | ✅ |
| Chat trực tiếp 1-1 | ✅ |
| Chat nhóm | ✅ |
| Peer discovery | ✅ |
| Trạng thái online/offline | ✅ |
| Truyền tin đáng tin cậy (ACK) | ✅ |
| Heartbeat & timeout | ✅ |
| Store-and-forward (offline msg) | ✅ (bonus) |
| Broadcast toàn mạng | ✅ (bonus) |
| Mã hoá tin nhắn (encryption) | ✅ (bonus) |
| File transfer giữa các peer | ✅ (bonus) |
| Giao diện GUI (Tkinter) | ✅ (bonus) |
| Mô phỏng churn | ✅ (bonus) |
| Đa luồng (gửi/nhận đồng thời) | ✅ |
| Xử lý peer disconnect | ✅ |

---

## Cấu trúc thư mục

```
p2p_chat/
├── config.py               Hằng số cấu hình
├── run_bootstrap.py        Entry point – bootstrap server
├── run_peer.py             Entry point – peer node
├── churn_sim.py            Mô phỏng churn (bot join/leave liên tục)
├── common/
│   ├── protocol.py         Định nghĩa message, encode/decode
│   ├── crypto.py           Mã hoá tin nhắn (PBKDF2 + HMAC, stdlib)
│   └── utils.py            Tiện ích
├── bootstrap/
│   └── server.py           Bootstrap/Tracker server
└── peer/
    ├── node.py             Peer node (orchestrator)
    ├── server.py           TCP server (nhận kết nối)
    ├── client.py           TCP client (gửi tin)
    ├── peer_manager.py     Quản lý danh sách peer & nhóm
    ├── cli.py              Giao diện dòng lệnh
    └── gui.py              Giao diện đồ hoạ (Tkinter)
```

Ngoài `run_bootstrap.py` và `run_peer.py` (CLI), còn có `run_gui.py` (GUI).

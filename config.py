BOOTSTRAP_HOST = "127.0.0.1"
BOOTSTRAP_PORT = 9000
DEFAULT_PEER_PORT = 9001

HEARTBEAT_INTERVAL = 15   # seconds between heartbeats sent to bootstrap
PEER_TIMEOUT = 60         # seconds before bootstrap drops a silent peer
CONNECT_TIMEOUT = 5       # socket connect timeout
RECV_TIMEOUT = 10         # socket recv timeout

# Mã hoá tin nhắn: passphrase chung của cả mạng. Mọi peer phải dùng cùng khoá
# này thì mới giải mã được cho nhau. Có thể đổi bằng tham số --key khi chạy.
NETWORK_SECRET = "p2p-chat-nhom7"

# Truyền file giữa các peer
DOWNLOAD_DIR = "downloads"      # thư mục lưu file nhận được
MAX_FILE_BYTES = 5 * 1024 * 1024   # giới hạn 5 MB/1 file (gửi trong 1 message)

"""
CLI – giao diện dòng lệnh tương tác cho peer node.

Lệnh hỗ trợ:
  list                              Danh sách peer đang online
  msg <tên> <nội dung>              Gửi tin nhắn trực tiếp
  groups                            Danh sách nhóm đã tham gia
  group create <tên> <p1> [p2 …]   Tạo nhóm mới
  group msg <tên_nhóm> <nội dung>   Gửi tin vào nhóm
  help                              Hiển thị trợ giúp
  quit / exit                       Thoát
"""

HELP = """
┌─────────────────────────────────────────────────────────────────┐
│  Lệnh                              Mô tả                        │
├─────────────────────────────────────────────────────────────────┤
│  list                              Xem peer đang online         │
│  msg <tên> <nội dung>              Nhắn tin trực tiếp           │
│  groups                            Xem danh sách nhóm           │
│  group create <tên> <p1> [p2 …]   Tạo nhóm mới                 │
│  group msg <tên_nhóm> <nội dung>   Gửi tin nhóm                 │
│  help                              Trợ giúp                     │
│  quit                              Thoát                        │
└─────────────────────────────────────────────────────────────────┘
"""


class CLI:
    def __init__(self, node):
        self.node = node
        node.set_display(self._show_incoming)

    # ------------------------------------------------------------------

    def _show_incoming(self, text: str):
        """In tin nhắn đến, rồi in lại prompt."""
        print(text)
        print(">>> ", end="", flush=True)

    def _ok(self, msg: str = ""):
        print(f"  [OK] {msg}" if msg else "  [OK]")

    def _err(self, msg: str):
        print(f"  [!]  {msg}")

    # ------------------------------------------------------------------

    def run(self):
        n = self.node
        print(HELP)
        print(f"  Tên:     {n.username}")
        print(f"  Địa chỉ: {n.host}:{n.port}")
        print(f"  ID:      {n.peer_id[:12]}…\n")

        while True:
            try:
                print(">>> ", end="", flush=True)
                line = input().strip()
            except (KeyboardInterrupt, EOFError):
                print()
                self._quit()
                break

            if not line:
                continue

            parts = line.split()
            cmd   = parts[0].lower()

            if cmd in ("quit", "exit", "q"):
                self._quit()
                break

            elif cmd == "help":
                print(HELP)

            elif cmd == "list":
                self._cmd_list()

            elif cmd == "msg":
                if len(parts) < 3:
                    self._err("Dùng: msg <tên> <nội dung>")
                else:
                    to_name = parts[1]
                    content = " ".join(parts[2:])
                    err = self.node.send_direct(to_name, content)
                    if err:
                        self._err(err)
                    else:
                        self._ok(f"→ {to_name}")

            elif cmd == "groups":
                self._cmd_groups()

            elif cmd == "group":
                self._cmd_group(parts)

            else:
                self._err(f"Lệnh không nhận ra: '{cmd}'. Gõ 'help'.")

    # ------------------------------------------------------------------
    # Sub-commands
    # ------------------------------------------------------------------

    def _quit(self):
        print("  Đang thoát…")
        self.node.stop()

    def _cmd_list(self):
        peers = self.node.get_online_peers()
        if not peers:
            print("  (Chưa có peer nào online)")
            return
        print(f"  Peers online ({len(peers)}):")
        for p in peers:
            print(f"    • {p.username:<20} {p.host}:{p.port}")

    def _cmd_groups(self):
        groups = self.node.get_groups()
        if not groups:
            print("  (Chưa tham gia nhóm nào)")
            return
        print(f"  Nhóm của bạn ({len(groups)}):")
        for g in groups:
            print(f"    • {g.group_name:<20} ({len(g.members)} thành viên)")

    def _cmd_group(self, parts):
        if len(parts) < 2:
            self._err("Dùng: group create … | group msg …")
            return

        sub = parts[1].lower()

        if sub == "create":
            if len(parts) < 4:
                self._err("Dùng: group create <tên_nhóm> <peer1> [peer2 …]")
                return
            group_name   = parts[2]
            member_names = parts[3:]
            err = self.node.create_group(group_name, member_names)
            if err:
                self._err(err)
            else:
                self._ok(f"Đã tạo nhóm '{group_name}'")

        elif sub == "msg":
            if len(parts) < 4:
                self._err("Dùng: group msg <tên_nhóm> <nội dung>")
                return
            group_name = parts[2]
            content    = " ".join(parts[3:])
            err = self.node.send_group(group_name, content)
            if err:
                self._err(err)
            else:
                self._ok(f"→ [{group_name}]")

        else:
            self._err(f"Lệnh group không nhận ra: '{sub}'")

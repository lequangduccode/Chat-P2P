"""
GUI – Giao diện đồ hoạ (Tkinter) cho peer node.

Chỉ dùng thư viện chuẩn (tkinter). Bọc quanh PeerNode có sẵn:
  - Không thay đổi logic mạng, chỉ thay CLI bằng cửa sổ chat.
  - Tin nhắn đến được đẩy vào giao diện qua callback set_display().

Luồng xử lý mạng (server thread) KHÔNG được đụng trực tiếp widget Tkinter,
nên mọi cập nhật giao diện đều đi qua root.after(0, ...) cho an toàn luồng.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, filedialog

from peer.node import PeerNode
from common.protocol import now_str
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, DEFAULT_PEER_PORT, NETWORK_SECRET


# Bảng màu
BG        = "#1e1f22"
PANEL     = "#2b2d31"
INPUT_BG  = "#383a40"
FG        = "#dbdee1"
MUTED     = "#949ba4"
ACCENT    = "#5865f2"
GREEN     = "#3ba55d"
BLUE      = "#00a8fc"
YELLOW    = "#faa61a"


class ChatGUI:
    def __init__(self):
        self.node: PeerNode | None = None
        self.target = None          # ("peer", username) | ("group", name) | None
        self.secret = NETWORK_SECRET   # khoá mã hoá mạng (run_gui.py có thể đổi)

        self.root = tk.Tk()
        self.root.title("P2P Chat – Nhóm 7")
        self.root.geometry("860x560")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_login()

    # ==================================================================
    # Màn hình đăng nhập
    # ==================================================================

    def _build_login(self):
        self.login = tk.Frame(self.root, bg=BG)
        self.login.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(self.login, text="P2P CHAT", font=("Segoe UI", 24, "bold"),
                 bg=BG, fg=ACCENT).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        tk.Label(self.login, text="Đồ án Các hệ thống phân tán – Chủ đề 3",
                 font=("Segoe UI", 9), bg=BG, fg=MUTED).grid(
                     row=1, column=0, columnspan=2, pady=(0, 20))

        self.e_user = self._field("Tên người dùng", 2, "")
        self.e_port = self._field("Cổng của bạn", 3, str(DEFAULT_PEER_PORT))
        self.e_bhost = self._field("Bootstrap host", 4, BOOTSTRAP_HOST)
        self.e_bport = self._field("Bootstrap port", 5, str(BOOTSTRAP_PORT))

        self.btn_connect = tk.Button(
            self.login, text="Kết nối", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="white", activebackground="#4752c4",
            relief="flat", width=28, cursor="hand2",
            command=self._do_connect)
        self.btn_connect.grid(row=6, column=0, columnspan=2, pady=(18, 0), ipady=6)

        self.root.bind("<Return>", lambda e: self._do_connect())
        self.e_user.focus_set()

    def _field(self, label, row, default):
        tk.Label(self.login, text=label, font=("Segoe UI", 9),
                 bg=BG, fg=MUTED, anchor="w").grid(
                     row=row, column=0, sticky="w", pady=(6, 0))
        e = tk.Entry(self.login, font=("Segoe UI", 11), width=30,
                     bg=INPUT_BG, fg=FG, insertbackground=FG, relief="flat")
        e.grid(row=row, column=1, padx=(10, 0), pady=(6, 0), ipady=4)
        e.insert(0, default)
        return e

    def _do_connect(self):
        username = self.e_user.get().strip()
        if not username:
            messagebox.showwarning("Thiếu thông tin", "Hãy nhập tên người dùng.")
            return
        try:
            port  = int(self.e_port.get())
            bport = int(self.e_bport.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng phải là số.")
            return
        bhost = self.e_bhost.get().strip() or BOOTSTRAP_HOST

        self.btn_connect.config(text="Đang kết nối…", state="disabled")

        def worker():
            node = PeerNode(username=username, port=port,
                            bootstrap_host=bhost, bootstrap_port=bport,
                            secret=self.secret)
            ok = False
            try:
                ok = node.start()
            except Exception as e:
                self.root.after(0, lambda: self._connect_failed(str(e)))
                return
            if ok:
                self.node = node
                self.root.after(0, self._build_main)
            else:
                self.root.after(0, lambda: self._connect_failed(
                    f"Không kết nối được Bootstrap tại {bhost}:{bport}.\n"
                    "Hãy chắc chắn đã chạy run_bootstrap.py trước."))

        threading.Thread(target=worker, daemon=True).start()

    def _connect_failed(self, reason):
        messagebox.showerror("Kết nối thất bại", reason)
        self.btn_connect.config(text="Kết nối", state="normal")

    # ==================================================================
    # Màn hình chat chính
    # ==================================================================

    def _build_main(self):
        self.root.unbind("<Return>")
        self.login.destroy()

        # ---- Thanh trên cùng ----
        top = tk.Frame(self.root, bg=PANEL, height=44)
        top.pack(side="top", fill="x")
        tk.Label(top, text=f"  {self.node.username}", font=("Segoe UI", 12, "bold"),
                 bg=PANEL, fg=FG).pack(side="left", pady=8)
        tk.Label(top, text=f"{self.node.host}:{self.node.port}   ",
                 font=("Segoe UI", 9), bg=PANEL, fg=MUTED).pack(side="right", pady=8)
        tk.Label(top, text="🔒 Mã hoá: BẬT   ", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=GREEN).pack(side="right", pady=8)

        # ---- Cột trái: peers + groups ----
        left = tk.Frame(self.root, bg=PANEL, width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="  PEERS ONLINE", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=MUTED, anchor="w").pack(fill="x", pady=(10, 2))
        self.lst_peers = tk.Listbox(
            left, bg=INPUT_BG, fg=FG, font=("Segoe UI", 10), height=10,
            relief="flat", selectbackground=ACCENT, highlightthickness=0,
            activestyle="none")
        self.lst_peers.pack(fill="x", padx=8)
        self.lst_peers.bind("<<ListboxSelect>>", self._on_pick_peer)

        tk.Label(left, text="  NHÓM", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=MUTED, anchor="w").pack(fill="x", pady=(14, 2))
        self.lst_groups = tk.Listbox(
            left, bg=INPUT_BG, fg=FG, font=("Segoe UI", 10), height=6,
            relief="flat", selectbackground=GREEN, highlightthickness=0,
            activestyle="none")
        self.lst_groups.pack(fill="x", padx=8)
        self.lst_groups.bind("<<ListboxSelect>>", self._on_pick_group)

        tk.Button(left, text="➕  Tạo nhóm", bg=INPUT_BG, fg=FG, relief="flat",
                  font=("Segoe UI", 10), cursor="hand2", activebackground=ACCENT,
                  command=self._dlg_create_group).pack(fill="x", padx=8, pady=(14, 4), ipady=4)
        tk.Button(left, text="📢  Broadcast toàn mạng", bg=INPUT_BG, fg=YELLOW,
                  relief="flat", font=("Segoe UI", 10), cursor="hand2",
                  activebackground=ACCENT,
                  command=self._do_broadcast).pack(fill="x", padx=8, ipady=4)

        # ---- Cột phải: khung chat ----
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self.lbl_target = tk.Label(
            right, text="  Chọn một peer hoặc nhóm ở bên trái để bắt đầu",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=MUTED, anchor="w")
        self.lbl_target.pack(fill="x", pady=(8, 4), padx=6)

        self.chat = scrolledtext.ScrolledText(
            right, bg=PANEL, fg=FG, font=("Consolas", 10), relief="flat",
            wrap="word", state="disabled", padx=10, pady=8)
        self.chat.pack(fill="both", expand=True, padx=6)
        self.chat.tag_config("sys",   foreground=MUTED, font=("Consolas", 9, "italic"))
        self.chat.tag_config("me",    foreground=GREEN)
        self.chat.tag_config("them",  foreground=BLUE)
        self.chat.tag_config("group", foreground="#c9a0ff")
        self.chat.tag_config("cast",  foreground=YELLOW)

        bottom = tk.Frame(right, bg=BG)
        bottom.pack(fill="x", padx=6, pady=8)
        self.entry = tk.Entry(bottom, bg=INPUT_BG, fg=FG, insertbackground=FG,
                              font=("Segoe UI", 11), relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self._do_send())
        tk.Button(bottom, text="Gửi", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), width=8, cursor="hand2",
                  activebackground="#4752c4",
                  command=self._do_send).pack(side="right", ipady=5)
        tk.Button(bottom, text="📎 File", bg=INPUT_BG, fg=FG, relief="flat",
                  font=("Segoe UI", 10), width=7, cursor="hand2",
                  activebackground=ACCENT,
                  command=self._do_send_file).pack(side="right", ipady=5, padx=(0, 6))

        # Kết nối callback tin nhắn đến + bắt đầu vòng cập nhật
        self.node.set_display(self._on_incoming)
        self._append("Đã kết nối vào mạng P2P. Sẵn sàng chat!\n", "sys")
        self._refresh_lists()

    # ==================================================================
    # Chọn đối tượng chat
    # ==================================================================

    def _on_pick_peer(self, _evt):
        sel = self.lst_peers.curselection()
        if not sel:
            return
        self.lst_groups.selection_clear(0, tk.END)
        name = self._peers_cache[sel[0]].username
        self.target = ("peer", name)
        self.lbl_target.config(text=f"  💬 Chat riêng với {name}", fg=BLUE)

    def _on_pick_group(self, _evt):
        sel = self.lst_groups.curselection()
        if not sel:
            return
        self.lst_peers.selection_clear(0, tk.END)
        name = self._groups_cache[sel[0]].group_name
        self.target = ("group", name)
        self.lbl_target.config(text=f"  👥 Chat nhóm {name}", fg=GREEN)

    # ==================================================================
    # Hành động
    # ==================================================================

    def _do_send(self):
        content = self.entry.get().strip()
        if not content:
            return
        if not self.target:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một peer hoặc nhóm trước.")
            return

        kind, name = self.target
        if kind == "peer":
            err = self.node.send_direct(name, content)
            if err:
                self._append(f"[{now_str()}] ⚠ {err}\n", "sys")
            else:
                self._append(f"[{now_str()}] Bạn → {name}: {content}\n", "me")
        else:  # group
            err = self.node.send_group(name, content)
            if err:
                self._append(f"[{now_str()}] ⚠ {err}\n", "sys")
            else:
                self._append(f"[{now_str()}] [{name}] Bạn: {content}\n", "me")

        self.entry.delete(0, tk.END)

    def _do_broadcast(self):
        content = simpledialog.askstring(
            "Broadcast", "Tin nhắn gửi tới TẤT CẢ peer online:", parent=self.root)
        if not content:
            return
        result = self.node.broadcast(content.strip())
        self._append(f"[{now_str()}] 📢 Bạn broadcast: {content}  ({result})\n", "cast")

    def _do_send_file(self):
        if not self.target or self.target[0] != "peer":
            messagebox.showinfo("Chọn peer", "Hãy chọn MỘT peer bên trái để gửi file.")
            return
        name = self.target[1]
        path = filedialog.askopenfilename(title=f"Chọn file gửi cho {name}",
                                          parent=self.root)
        if not path:
            return
        err = self.node.send_file(name, path)
        if err:
            self._append(f"[{now_str()}] ⚠ {err}\n", "sys")
        else:
            self._append(f"[{now_str()}] 📎 Bạn gửi file '{os.path.basename(path)}' "
                         f"→ {name} (đã mã hoá)\n", "me")

    def _dlg_create_group(self):
        peers = self.node.get_online_peers()
        if not peers:
            messagebox.showinfo("Không có peer", "Chưa có peer nào online để tạo nhóm.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Tạo nhóm mới")
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Tên nhóm:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(14, 2))
        e_name = tk.Entry(dlg, bg=INPUT_BG, fg=FG, insertbackground=FG,
                          font=("Segoe UI", 11), width=30, relief="flat")
        e_name.pack(padx=14, ipady=4)
        e_name.focus_set()

        tk.Label(dlg, text="Chọn thành viên:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(12, 2))
        vars_ = []
        for p in peers:
            v = tk.IntVar()
            tk.Checkbutton(dlg, text=f"{p.username}  ({p.host}:{p.port})",
                           variable=v, bg=BG, fg=FG, selectcolor=PANEL,
                           activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 10)).pack(anchor="w", padx=20)
            vars_.append((v, p.username))

        def confirm():
            gname = e_name.get().strip()
            members = [name for v, name in vars_ if v.get()]
            if not gname:
                messagebox.showwarning("Thiếu tên", "Nhập tên nhóm.", parent=dlg)
                return
            if not members:
                messagebox.showwarning("Thiếu thành viên", "Chọn ít nhất 1 peer.", parent=dlg)
                return
            err = self.node.create_group(gname, members)
            if err:
                messagebox.showerror("Lỗi", err, parent=dlg)
                return
            self._append(f"Đã tạo nhóm '{gname}' với: {', '.join(members)}\n", "sys")
            self._refresh_lists()
            dlg.destroy()

        tk.Button(dlg, text="Tạo nhóm", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2",
                  command=confirm).pack(pady=14, ipadx=10, ipady=4)

    # ==================================================================
    # Tin nhắn đến (chạy trên server thread → marshal về Tk thread)
    # ==================================================================

    def _on_incoming(self, text: str):
        t = text.strip("\n")
        if "📎" in t:                 tag = "cast"
        elif ">>" in t:               tag = "sys"
        elif "→ bạn" in t:            tag = "them"
        elif "BROADCAST" in t:        tag = "cast"
        elif t.startswith("[") and "] [" in t:  tag = "group"
        else:                         tag = "them"
        self.root.after(0, lambda: self._append(t + "\n", tag))

    def _append(self, text: str, tag: str = None):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, text, tag)
        self.chat.see(tk.END)
        self.chat.config(state="disabled")

    # ==================================================================
    # Cập nhật định kỳ danh sách peer & nhóm
    # ==================================================================

    def _refresh_lists(self):
        self._peers_cache = self.node.get_online_peers()
        self._groups_cache = self.node.get_groups()

        self.lst_peers.delete(0, tk.END)
        for p in self._peers_cache:
            self.lst_peers.insert(tk.END, f"🟢 {p.username}")
        if not self._peers_cache:
            self.lst_peers.insert(tk.END, "(chưa có ai online)")

        self.lst_groups.delete(0, tk.END)
        for g in self._groups_cache:
            self.lst_groups.insert(tk.END, f"👥 {g.group_name} ({len(g.members)})")

        self.root.after(2000, self._refresh_lists)   # lặp mỗi 2s

    # ==================================================================
    # Vòng đời
    # ==================================================================

    def _on_close(self):
        try:
            if self.node:
                self.node.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()

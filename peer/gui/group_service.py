"""Group membership operations kept outside the Qt widgets."""
from common.protocol import MsgType, make_msg


def add_members_to_group(node, group_name: str, usernames: list[str]) -> str | None:
    group = node.manager.get_group_by_name(group_name)
    if not group:
        return f"Không tìm thấy nhóm '{group_name}'"

    new_peer_ids: list[str] = []
    missing: list[str] = []
    for username in usernames:
        peer = node.manager.get_peer_by_name(username)
        if not peer:
            missing.append(username)
            continue
        if peer.peer_id not in group.members:
            node.manager.add_member(group.group_id, peer.peer_id)
            new_peer_ids.append(peer.peer_id)

    if missing:
        return f"Không tìm thấy peer: {', '.join(missing)}"
    if not new_peer_ids:
        return "Các peer đã chọn đều đã có trong nhóm"

    # Send the complete member list to every member so all peers converge
    # to the same distributed group state.
    invite = make_msg(
        MsgType.GROUP_INVITE,
        from_id=node.peer_id,
        from_name=node.username,
        group_id=group.group_id,
        group_name=group.group_name,
        members=list(group.members),
    )

    failed: list[str] = []
    for member_id in list(group.members):
        if member_id == node.peer_id:
            continue
        peer = node.manager.get_peer(member_id)
        if not peer:
            continue
        if not peer.online or not node.client.send_to_peer(peer.host, peer.port, invite):
            # Preserve the membership update for reconnecting peers when possible.
            try:
                node.client.store_offline(peer.username, invite)
            except Exception:
                pass
            failed.append(peer.username)

    if failed:
        return "Đã thêm thành viên; cập nhật đang chờ gửi tới: " + ", ".join(failed)
    return None

"""Minimal ACPI generic-netlink listener for Xiaomi WMI notifications."""

from __future__ import annotations

import socket
import struct


FAMILY = b"acpi_event\0"
GROUP = b"acpi_mc_group\0"
NETLINK_GENERIC = 16
SOL_NETLINK = 270
NETLINK_ADD_MEMBERSHIP = 1
GENL_ID_CTRL = 0x10
NLM_F_REQUEST = 1
NLMSG_ERROR = 2
CTRL_CMD_GETFAMILY = 3
CTRL_ATTR_FAMILY_NAME = 2
CTRL_ATTR_MCAST_GROUPS = 7
CTRL_ATTR_MCAST_GRP_NAME = 1
CTRL_ATTR_MCAST_GRP_ID = 2
ATTR_EVENT = 1


def _attributes(data):
    offset = 0
    while offset + 4 <= len(data):
        length, kind = struct.unpack_from("=HH", data, offset)
        if length < 4 or offset + length > len(data):
            return
        yield kind & 0x3FFF, data[offset + 4:offset + length]
        offset += (length + 3) & ~3


def _messages(data):
    offset = 0
    while offset + 16 <= len(data):
        length, kind = struct.unpack_from("=IH", data, offset)
        if length < 16 or offset + length > len(data):
            return
        yield kind, data[offset + 16:offset + length]
        offset += (length + 3) & ~3


def _cstring(data):
    return data.split(b"\0", 1)[0].decode("utf-8", "replace")


def parse_events(data):
    """Return (device class, bus ID, notification kind) tuples."""
    events = []
    for _, body in _messages(data):
        if len(body) < 4:
            continue
        for kind, event in _attributes(body[4:]):
            if kind != ATTR_EVENT or len(event) < 44:
                continue
            events.append((
                _cstring(event[:20]),
                _cstring(event[20:35]),
                struct.unpack_from("=I", event, 36)[0],
            ))
    return events


class AcpiEventListener:
    def __init__(self):
        self.socket = socket.socket(
            socket.AF_NETLINK,
            socket.SOCK_RAW | getattr(socket, "SOCK_CLOEXEC", 0),
            NETLINK_GENERIC,
        )
        self.socket.bind((0, 0))
        group = self._resolve_group()
        self.socket.setsockopt(SOL_NETLINK, NETLINK_ADD_MEMBERSHIP, struct.pack("=I", group))

    def fileno(self):
        return self.socket.fileno()

    def close(self):
        self.socket.close()

    def _resolve_group(self):
        attribute = struct.pack("=HH", 4 + len(FAMILY), CTRL_ATTR_FAMILY_NAME) + FAMILY
        attribute += bytes((-len(attribute)) % 4)
        payload = struct.pack("=BBBB", CTRL_CMD_GETFAMILY, 1, 0, 0) + attribute
        header = struct.pack("=IHHII", 16 + len(payload), GENL_ID_CTRL, NLM_F_REQUEST, 1, 0)
        self.socket.send(header + payload)
        response = self.socket.recv(8192)
        for kind, body in _messages(response):
            if kind == NLMSG_ERROR:
                error = struct.unpack_from("=i", body)[0]
                if error:
                    raise OSError(-error, "ACPI generic-netlink family lookup failed")
            if len(body) < 4:
                continue
            for attr_kind, groups in _attributes(body[4:]):
                if attr_kind != CTRL_ATTR_MCAST_GROUPS:
                    continue
                for _, group_data in _attributes(groups):
                    fields = dict(_attributes(group_data))
                    name = fields.get(CTRL_ATTR_MCAST_GRP_NAME)
                    group_id = fields.get(CTRL_ATTR_MCAST_GRP_ID)
                    if name and group_id and _cstring(name).encode() == GROUP.rstrip(b"\0"):
                        return struct.unpack("=I", group_id[:4])[0]
        raise OSError("ACPI multicast group acpi_mc_group not found")

    def next_events(self):
        return parse_events(self.socket.recv(8192))

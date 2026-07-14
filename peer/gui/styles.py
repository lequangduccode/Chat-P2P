APP_STYLE = r"""
* {
    font-family: "Segoe UI", "Arial";
    font-size: 14px;
    color: #172033;
}
QMainWindow, QDialog {
    background: #f3f6fb;
}
QFrame#sidebar {
    background: #14295f;
    border: none;
}
QLabel#brand {
    color: #ffffff;
    font-size: 24px;
    font-weight: 800;
}
QLabel#mutedOnDark { color: #bfd1ff; }
QLabel#cryptoOnDark { color: #83f3c2; font-size: 11px; font-weight: 700; padding-top: 2px; }
QLabel#sectionTitle {
    color: #718096;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
}
QLabel#chatTitle {
    color: #101828;
    font-size: 20px;
    font-weight: 800;
}
QLabel#chatSubtitle { color: #667085; font-size: 13px; }

QFrame#navigator {
    background: #f8fafc;
    border-right: 1px solid #e3eaf3;
}
QFrame#chatArea, QFrame#topbar, QFrame#composer {
    background: #ffffff;
    border: none;
}
QFrame#topbar { border-bottom: 1px solid #e7edf5; }
QFrame#composer { border-top: 1px solid #e7edf5; }

QWidget#messageCanvas,
QScrollArea#messageScroll,
QScrollArea#messageScroll > QWidget,
QScrollArea#messageScroll QWidget#qt_scrollarea_viewport {
    background: #f4f7fb;
    border: none;
}

/* Message bubbles */
QWidget#messageRow {
    background: transparent;
}
QFrame#incomingBubble {
    background: #ffffff;
    border: 1px solid #dfe7f1;
    border-radius: 16px;
}
QFrame#outgoingBubble {
    background: #2f6fed;
    border: 1px solid #2f6fed;
    border-radius: 16px;
}
QLabel#messageAuthor {
    background: transparent;
    border: none;
    color: #245ed4;
    font-size: 12px;
    font-weight: 700;
    padding: 0;
}
QLabel#incomingMessageText {
    background: transparent;
    border: none;
    color: #172033;
    font-size: 14px;
    padding: 0;
}
QLabel#outgoingMessageText {
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 14px;
    padding: 0;
}
QLabel#incomingMessageMeta {
    background: transparent;
    border: none;
    color: #98a2b3;
    font-size: 10px;
    padding: 0;
}
QLabel#outgoingMessageMeta {
    background: transparent;
    border: none;
    color: #d7e4ff;
    font-size: 10px;
    padding: 0;
}

/* Inputs and buttons */
QLineEdit, QTextEdit {
    background: #ffffff;
    border: 1px solid #d6dfeb;
    border-radius: 11px;
    padding: 10px 13px;
    color: #182230;
    selection-background-color: #2f6fed;
}
QLineEdit:hover, QTextEdit:hover { border-color: #b8c5d6; }
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #2f6fed;
    background: #ffffff;
}
QLineEdit:disabled { background: #f2f4f7; color: #98a2b3; }

QPushButton {
    min-height: 20px;
    background: #2f6fed;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover { background: #245ed4; }
QPushButton:pressed { background: #1d4fb7; }
QPushButton:disabled {
    background: #d9e2f0;
    color: #98a6ba;
}
QPushButton#secondary {
    background: #eef3fb;
    color: #24478f;
    border: 1px solid #d8e2f2;
}
QPushButton#secondary:hover { background: #e0e9f7; }
QPushButton#ghost {
    background: transparent;
    color: #315baf;
    border: 1px solid #d6dfeb;
}
QPushButton#ghost:hover { background: #f2f6fc; }
QPushButton#danger { background: #d92d20; }

/* Main navigator list */
QListWidget {
    background: transparent;
    border: none;
    outline: none;
    padding: 0;
}
QListWidget::item {
    background: transparent;
    border: none;
    border-radius: 12px;
    margin: 2px 0;
    padding: 0;
}
QListWidget::item:hover { background: #edf3fb; }
QListWidget::item:selected { background: #e1ebfb; }

/* Group member dialogs */
QDialog#groupDialog {
    background: #f6f8fc;
}
QLabel#dialogTitle {
    color: #101828;
    font-size: 21px;
    font-weight: 800;
}
QLabel#dialogHint {
    color: #667085;
    font-size: 13px;
    line-height: 1.4;
}
QLabel#dialogSectionTitle {
    color: #667085;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
}
QFrame#dialogCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
}
QLabel#memberSummary {
    background: #eaf1ff;
    color: #315baf;
    border: 1px solid #d6e3fb;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
}
QListWidget#dialogPeerList {
    background: #ffffff;
    border: 1px solid #e0e7f0;
    border-radius: 14px;
    padding: 7px;
    outline: none;
}
QListWidget#dialogPeerList::item {
    background: transparent;
    border: none;
    border-radius: 11px;
    margin: 2px 0;
    padding: 0;
}
QListWidget#dialogPeerList::item:hover {
    background: #f2f6fc;
}
QListWidget#dialogPeerList::item:disabled {
    background: #f7f9fc;
}
QWidget#peerDialogRow {
    background: transparent;
}

QCheckBox#peerCheckBox {
    background: transparent;
    border: none;
    padding: 0;
}
QLabel#dialogPeerAvatar {
    background: #e7efff;
    color: #245ed4;
    border: none;
    border-radius: 18px;
    font-weight: 800;
}
QLabel#dialogPeerName {
    background: transparent;
    border: none;
    color: #172033;
    font-weight: 700;
}
QLabel#dialogPeerOnline {
    background: transparent;
    border: none;
    color: #17a35b;
    font-size: 11px;
}
QLabel#dialogPeerOffline {
    background: transparent;
    border: none;
    color: #98a2b3;
    font-size: 11px;
}
QLabel#existingMemberBadge {
    background: #edf2f7;
    color: #667085;
    border: 1px solid #dde4ed;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#emptyPeerNotice {
    color: #98a2b3;
    padding: 10px;
}
QDialogButtonBox#dialogActions {
    background: transparent;
}
QDialogButtonBox#dialogActions QPushButton {
    min-width: 128px;
    min-height: 22px;
}

/* Scrollbars and status */
QScrollBar:vertical {
    width: 10px;
    margin: 2px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #c2ccda;
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #aab7c8; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

QStatusBar {
    background: #ffffff;
    color: #667085;
    border-top: 1px solid #e7edf5;
}
QToolTip {
    background: #101828;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 8px;
}

/* Conversation rows */
QWidget#conversationRow {
    background: transparent;
    border: none;
    min-height: 64px;
    max-height: 64px;
}
QWidget#conversationStatus,
QWidget#unreadBadgeSlot {
    background: transparent;
    border: none;
}
QLabel#unreadBadgePlaceholder {
    background: transparent;
    border: none;
}
QLabel#conversationAvatar {
    background: #dce9ff;
    color: #2259b8;
    border: none;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 800;
}
QLabel#conversationName {
    background: transparent;
    color: #101828;
    border: none;
    font-size: 14px;
    font-weight: 700;
    padding: 0;
    margin: 0;
}
QLabel#conversationSubtitle {
    background: transparent;
    color: #667085;
    border: none;
    font-size: 12px;
    padding: 0;
    margin: 0;
}
QLabel#onlineDot {
    background: transparent;
    color: #22b573;
    border: none;
    font-size: 9px;
    padding: 0;
    margin: 0;
}
QLabel#offlineDot {
    background: transparent;
    color: #98a2b3;
    border: none;
    font-size: 10px;
}
QLabel#unreadBadge {
    background: #f04438;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 800;
}


QPushButton#attachButton {
    background: #eef3fb;
    color: #315baf;
    border: 1px solid #d8e2f2;
    border-radius: 12px;
    padding: 0;
    font-size: 19px;
}
QPushButton#attachButton:hover { background: #e0e9f7; }
QPushButton#attachButton:disabled {
    background: #f2f4f7;
    color: #b7c0ce;
    border-color: #e4e7ec;
}
QWidget#fileTransferRow { background: transparent; }
QFrame#incomingFileCard {
    background: #ffffff;
    border: 1px solid #dfe7f1;
    border-radius: 16px;
}
QFrame#outgoingFileCard {
    background: #eaf1ff;
    border: 1px solid #bfd3fb;
    border-radius: 16px;
}
QLabel#fileIcon {
    background: #ffffff;
    border: 1px solid #d9e4f5;
    border-radius: 10px;
    font-size: 20px;
}
QLabel#fileName {
    background: transparent;
    border: none;
    color: #172033;
    font-weight: 750;
}
QLabel#fileMeta, QLabel#fileStatus {
    background: transparent;
    border: none;
    color: #667085;
    font-size: 11px;
}
QLabel#fileStatusError {
    background: transparent;
    border: none;
    color: #d92d20;
    font-size: 11px;
}
QProgressBar#fileProgress {
    min-height: 7px;
    max-height: 7px;
    background: #dce5f2;
    border: none;
    border-radius: 3px;
}
QProgressBar#fileProgress::chunk {
    background: #2f6fed;
    border-radius: 3px;
}
QPushButton#fileCancelButton, QPushButton#fileOpenButton {
    min-height: 16px;
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 11px;
}
QPushButton#fileCancelButton {
    background: #fff1f0;
    color: #b42318;
    border: 1px solid #fecdca;
}
QPushButton#fileOpenButton {
    background: #2f6fed;
    color: #ffffff;
}

"""

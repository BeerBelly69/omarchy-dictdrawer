import QtQuick

// Printable keys belong to search, never to letter-based navigation.
Item {
  id: root
  property bool blocked: false
  signal moveRequested(int dx, int dy)
  signal activateRequested()
  signal closeRequested()
  signal searchRequested()
  signal textKey(string text)
  focus: true
  Keys.priority: Keys.BeforeItem
  Keys.onPressed: function(event) {
    if (blocked) return
    if (event.key === Qt.Key_F && (event.modifiers & Qt.ControlModifier)) {
      searchRequested()
    } else if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) {
      return
    } else if (event.key === Qt.Key_Escape) {
      closeRequested()
    } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
      searchRequested()
    } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
      moveRequested(0, event.key === Qt.Key_Down ? 1 : -1)
    } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
      moveRequested(event.key === Qt.Key_Right ? 1 : -1, 0)
    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      activateRequested()
    } else if (event.text && !/[\x00-\x1f\x7f]/.test(event.text)) {
      textKey(event.text)
    } else return
    event.accepted = true
  }
}

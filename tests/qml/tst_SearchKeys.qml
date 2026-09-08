import QtQuick
import QtTest
import "../.." as App

Item {
  width: 640
  height: 400
  App.SearchKeyCatcher {
    id: catcher
    anchors.fill: parent
    property var calls: []
    onTextKey: function(text) { calls.push(["text", text]) }
    onMoveRequested: function(dx, dy) { calls.push(["move", dx, dy]) }
    onActivateRequested: calls.push(["copy"])
    onCloseRequested: calls.push(["escape"])
    onSearchRequested: calls.push(["search"])
    TextInput { id: editor; width: 300; height: 30 }
  }
  TestCase {
    name: "TypeToSearch"
    when: windowShown
    function init() {
      catcher.blocked = false
      catcher.calls = []
      catcher.forceActiveFocus()
      editor.text = ""
    }
    function test_printable_data() {
      return [
        {tag: "j", key: Qt.Key_J, text: "j"},
        {tag: "k", key: Qt.Key_K, text: "k"},
        {tag: "h", key: Qt.Key_H, text: "h"},
        {tag: "l", key: Qt.Key_L, text: "l"},
        {tag: "x", key: Qt.Key_X, text: "x"},
        {tag: "f", key: Qt.Key_F, text: "f"},
        {tag: "slash", key: Qt.Key_Slash, text: "/"},
        {tag: "space", key: Qt.Key_Space, text: " "}
      ]
    }
    function test_printable(data) {
      keyClick(data.key)
      compare(JSON.stringify(catcher.calls), JSON.stringify([["text", data.text]]))
    }
    function test_uppercase() {
      keyClick("J")
      compare(catcher.calls[0][1], "J")
    }
    function test_navigation() {
      keyClick(Qt.Key_Down); keyClick(Qt.Key_Up)
      keyClick(Qt.Key_Left); keyClick(Qt.Key_Right)
      compare(JSON.stringify(catcher.calls), JSON.stringify([["move",0,1],["move",0,-1],["move",-1,0],["move",1,0]]))
    }
    function test_shortcuts() {
      keyClick(Qt.Key_F, Qt.ControlModifier)
      keyClick(Qt.Key_Tab)
      keyClick(Qt.Key_Return)
      keyClick(Qt.Key_Escape)
      compare(JSON.stringify(catcher.calls), JSON.stringify([["search"],["search"],["copy"],["escape"]]))
    }
    function test_other_modifiers_do_not_start_search() {
      keyClick(Qt.Key_C, Qt.ControlModifier)
      keyClick(Qt.Key_D, Qt.MetaModifier | Qt.AltModifier)
      compare(catcher.calls.length, 0)
    }
    function test_editor_keeps_letters_spaces_and_caret_keys() {
      catcher.blocked = true
      editor.forceActiveFocus()
      keyClick(Qt.Key_J); keyClick(Qt.Key_K); keyClick(Qt.Key_Space)
      keyClick(Qt.Key_H); keyClick(Qt.Key_L)
      keyClick(Qt.Key_Left); keyClick(Qt.Key_Backspace)
      compare(editor.text, "jk l")
      compare(catcher.calls.length, 0)
    }
  }
}

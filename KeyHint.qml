import QtQuick
import qs.Commons

Row {
  id: root
  required property string keys
  required property string label
  spacing: Style.space(5)

  Rectangle {
    anchors.verticalCenter: parent.verticalCenter
    width: keyText.implicitWidth + Style.space(10)
    height: keyText.implicitHeight + Style.space(6)
    radius: Style.space(4)
    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.06)
    border.width: 1
    border.color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.1)
    Text {
      id: keyText
      anchors.centerIn: parent
      text: root.keys
      color: Color.foreground
      opacity: 0.75
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }
  }
  Text {
    anchors.verticalCenter: parent.verticalCenter
    text: root.label
    color: Color.foreground
    opacity: 0.55
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
  }
}

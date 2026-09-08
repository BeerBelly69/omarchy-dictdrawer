import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import "Plugin" as Plugin

ShellRoot {
  // Safety net in addition to the Python runner's finally cleanup.
  Timer { interval: 180000; running: true; onTriggered: Qt.quit() }
  PanelWindow {
    id: backdrop
    screen: Quickshell.screens.find(s => s.name === "DICTDRAWER-QA")
    visible: Quickshell.screens.some(s => s.name === "DICTDRAWER-QA")
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "dictdrawer-qa-backdrop"
    color: "#161e25"
    Rectangle {
      anchors.fill: parent
      gradient: Gradient {
        GradientStop { position: 0; color: "#172d35" }
        GradientStop { position: 1; color: "#14151c" }
      }
    }
  }
  PanelWindow {
    id: previewBar
    screen: backdrop.screen
    visible: backdrop.visible
    anchors { top: position !== "bottom"; bottom: position !== "top"; left: position !== "right"; right: position !== "left" }
    implicitHeight: barSize
    implicitWidth: barSize
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "dictdrawer-qa-bar"
    color: "#0f131a"
    property string position: "top"
    property bool vertical: position === "left" || position === "right"
    property int barSize: 38
    property color foreground: Color.foreground
    property color barForeground: foreground
    property color urgent: Color.urgent
    property string fontFamily: Style.font.family
    property bool foregroundAnimationEnabled: false
    property var activePopout: null
    property var clickTargets: []
    function hideTooltip(item) {}
    function showTooltip(item, text) {}
    function registerClickTarget(item) { clickTargets = [item] }
    function unregisterClickTarget(item) { clickTargets = [] }
    function requestPopout(item) { activePopout = item }
    function releasePopout(item) { activePopout = null }
    Plugin.Panel {
      id: widget
      anchors.centerIn: parent
      bar: previewBar
    }
  }
  IpcHandler {
    target: "preview"
    function setup(side: string, thickness: int, fontSize: int): void {
      widget.close()
      previewBar.position = side
      previewBar.barSize = thickness
      Style.fontBaseSize = fontSize
      Style.spacingScale = 1
      Style.spacingScaleWithFont = true
      reopen.restart()
    }
    function query(value: string): void { widget.qaQuery(value) }
    function close(): void { widget.close() }
    function state(): string { return widget.qaState() }
    function quit(): void { Qt.quit() }
  }
  Timer { id: reopen; interval: 100; onTriggered: widget.open() }
}

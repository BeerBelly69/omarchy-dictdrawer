import QtQuick
import QtQuick.Controls
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Recover Voxtype output from the user journal and the local transcript archive.
Panel {
  id: root
  moduleName: "dictdrawer"
  // Use the shell's monitor-aware routing, avoiding duplicate IPC handlers
  // when the bar instantiates one widget on each output.
  // omarchy-shell shell toggle dictdrawer
  manageIpc: false

  readonly property string home: Quickshell.env("HOME")
  readonly property int limit: Math.max(5, Math.min(100, Number(root.setting("limit", 20)) || 20))
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("history.py").toString().replace(/^file:\/\//, ""))
  property string archiveDir: (Quickshell.env("XDG_DATA_HOME") || (root.home + "/.local/share")) + "/voxtype/history"

  property var rows: []
  property string resultsQuery: ""
  property bool loaded: false
  property string copiedId: ""
  property int expandedIndex: -1
  property int selectedIndex: 0
  property string errorMessage: ""
  property string historyWarning: ""
  property int matched: 0
  property int total: 0
  property bool searchShown: false
  property bool syncPending: false
  property bool refreshPending: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // ---------- recording state ----------
  // The daemon rewrites this file on every transition (idle / recording /
  // transcribing), which is cheaper to watch than polling `voxtype status`.
  property string state: "idle"

  FileView {
    path: Quickshell.env("XDG_RUNTIME_DIR") + "/voxtype/state"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var next = String(text() || "").trim()
      root.state = next.length > 0 ? next : "idle"
      // Archive completed dictations while the widget is enabled, even closed.
      if (root.state === "idle") refreshTimer.restart()
    }
    onLoadFailed: root.state = "idle"
  }


  // ---------- history ----------
  Process {
    id: historyProc
    property string requestQuery: ""
    property bool requestSync: false
    stdout: StdioCollector { id: historyOutput; waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      historyTimeout.stop()
      if (requestQuery === searchField.text) {
        try {
          var parsed = JSON.parse(historyOutput.text)
          if (exitCode !== 0 || parsed.error || !Array.isArray(parsed.rows))
            throw new Error(parsed.error || "Could not load history. Try Refresh.")
          if (root.resultsQuery !== requestQuery) {
            root.selectedIndex = 0
            root.expandedIndex = -1
          }
          root.rows = parsed.rows
          root.resultsQuery = requestQuery
          root.total = parsed.total
          root.matched = parsed.matched
          root.archiveDir = parsed.archiveDir
          if (requestSync) root.historyWarning = parsed.warning || ""
          root.errorMessage = ""
          root.selectedIndex = Math.min(root.selectedIndex, Math.max(0, root.rows.length - 1))
        } catch (error) {
          root.errorMessage = "Could not load history. Check Python 3 and archive permissions, then Refresh."
        }
      }
      root.loaded = true
      if (root.refreshPending || requestQuery !== searchField.text)
        Qt.callLater(function() { root.refresh(false) })
    }
  }

  function refresh(sync) {
    if (sync !== false) syncPending = true
    if (historyTimeout.running) { refreshPending = true; return }
    refreshPending = false
    historyProc.requestQuery = searchField.text
    historyProc.requestSync = syncPending
    var command = ["python3", helperPath, "--limit", String(limit), "--query", searchField.text]
    if (!syncPending) command.push("--no-sync")
    syncPending = false
    historyProc.command = command
    historyTimeout.restart()
    historyProc.running = true
  }

  Timer {
    id: historyTimeout
    interval: 15000
    onTriggered: {
      historyProc.running = false
      root.loaded = true
      root.errorMessage = "History timed out or could not start. Check Python 3, then Refresh."
    }
  }

  Timer {
    id: searchTimer
    interval: 160
    onTriggered: root.refresh(false)
  }

  // The state file flips to idle a beat before the daemon logs the text, so
  // give the journal a moment to catch up rather than reading an empty tail.
  Timer {
    id: refreshTimer
    interval: 600
    onTriggered: root.refresh()
  }

  onOpenedChanged: {
    if (opened) {
      copiedId = ""
      expandedIndex = -1
      selectedIndex = 0
      refresh()
    }
  }

  function copy(index) {
    var row = rows[index]
    if (!row || resultsQuery !== searchField.text || copyTimeout.running || searchTimer.running || historyTimeout.running) return
    errorMessage = ""
    copyProc.rowId = row.id
    copyProc.transcript = String(row.text)
    copyProc.stdinEnabled = true
    copyTimeout.restart()
    copyProc.running = true
  }

  Process {
    id: copyProc
    property string rowId: ""
    property string transcript: ""
    command: ["wl-copy", "--type", "text/plain;charset=utf-8"]
    stderr: StdioCollector { waitForEnd: true }
    stdinEnabled: true
    onStarted: {
      write(transcript)
      stdinEnabled = false
      transcript = ""
    }
    onExited: function(exitCode) {
      copyTimeout.stop()
      if (exitCode === 0) {
        root.copiedId = rowId
        copiedReset.restart()
      } else root.errorMessage = "Copy failed. Check that wl-clipboard is installed and the Wayland clipboard is available."
    }
  }

  Timer {
    id: copyTimeout
    interval: 5000
    onTriggered: {
      copyProc.running = false
      copyProc.transcript = ""
      root.errorMessage = "Copy could not start or timed out. Check wl-clipboard."
    }
  }

  Process {
    id: folderProc
    command: ["xdg-open", root.archiveDir]
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      folderTimeout.stop()
      if (exitCode === 0) root.close()
      else root.errorMessage = "Could not open the history folder. Check xdg-utils and your file manager."
    }
  }

  Timer {
    id: folderTimeout
    interval: 10000
    onTriggered: {
      folderProc.running = false
      root.errorMessage = "Could not open the history folder. Check xdg-utils and your file manager."
    }
  }

  function search(initialText) {
    searchShown = true
    searchField.forceActiveFocus()
    if (typeof initialText === "string") {
      searchField.text = initialText
      searchField.cursorPosition = searchField.text.length
    } else searchField.selectAll()
  }

  function escapeSearch() {
    if (searchField.text.length) {
      searchField.clear()
      searchShown = false
      keyCatcher.forceActiveFocus()
    } else {
      searchShown = false
      close()
    }
  }

  function moveSelection(dy, dx) {
    if (!rows.length) return
    selectedIndex = Math.max(0, Math.min(rows.length - 1, selectedIndex + dy))
    if (dx !== 0) expandedIndex = dx > 0 ? selectedIndex : -1
    list.positionViewAtIndex(selectedIndex, ListView.Contain)
  }

  Timer {
    id: copiedReset
    interval: 1400
    onTriggered: root.copiedId = ""
  }

  function stamp(ts) {
    var when = new Date(Number(ts) * 1000)
    var now = new Date()
    var sameDay = when.toDateString() === now.toDateString()
    var time = Qt.formatDateTime(when, "h:mm AP")
    return sameDay ? time : Qt.formatDateTime(when, "MMM d") + " " + time
  }

  // ---------- bar button ----------
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // A history glyph, not a mic: omarchy.indicators sits immediately to the
    // right and already flashes 󰍬 / 󰔟 while voxtype is recording and
    // transcribing. This button is the archive, and it is always there.
    text: "󰋚"
    tooltipText: "DictDrawer"
    onPressed: function(b) { root.toggle() }
  }

  // ---------- dropdown ----------
  DrawerPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(620))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    SearchKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: searchField.activeFocus
      onCloseRequested: root.escapeSearch()
      onMoveRequested: function(dx, dy) { root.moveSelection(dy, dx) }
      onActivateRequested: root.copy(root.selectedIndex)
      onTextKey: function(text) { root.search(text) }
      onSearchRequested: root.search()

      Column {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(14)

        Text {
          id: statusMessage
          width: parent.width
          visible: text.length > 0
          text: root.errorMessage || root.historyWarning
          textFormat: Text.PlainText
          color: Color.urgent
          wrapMode: Text.WordWrap
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.caption
        }

        Item {
          id: resultsArea
          width: parent.width
          // Keep the drawer and footer still for loading, few/zero matches,
          // and each debounced query. Only available screen space limits it.
          height: Math.max(0, Math.min(Style.space(460), panel.availableCardHeight - panel.verticalContentInset - footer.implicitHeight - column.spacing - (statusMessage.visible ? statusMessage.implicitHeight + column.spacing : 0)))

          Text {
            width: parent.width
            visible: root.rows.length === 0
            text: historyTimeout.running || searchTimer.running ? "Loading dictations…"
              : searchField.text.trim() ? "No matching dictations. Try different words."
              : "No dictations yet. Start Voxtype and dictate to save your first excerpt."
            color: root.bar.foreground
            opacity: 0.6
            wrapMode: Text.WordWrap
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          ListView {
            id: list
            anchors.fill: parent
            visible: root.rows.length > 0
            spacing: Style.space(8)
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            model: root.rows

            delegate: Rectangle {
              required property var modelData
              required property int index

              width: list.width
              implicitHeight: rowContent.implicitHeight + Style.space(24)
              radius: Style.space(10)
              border.width: 1
              border.color: root.selectedIndex === index
                ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.4) : "transparent"
              color: hover.hovered || root.selectedIndex === index
                ? Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.08)
                : Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.03)

              Behavior on color { ColorAnimation { duration: 100 } }
              HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }

              readonly property bool expanded: root.expandedIndex === index

              TapHandler {
                acceptedButtons: Qt.LeftButton
                onTapped: {
                  root.selectedIndex = index
                  root.expandedIndex = expanded ? -1 : index
                }
              }

              Column {
                id: rowContent
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Style.space(12)
                spacing: Style.space(4)

                Item {
                  width: parent.width
                  implicitHeight: Math.max(timeLabel.implicitHeight, copyButton.implicitHeight)

                  Text {
                    id: chevron
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "󰅂"
                    color: root.bar.foreground
                    opacity: hover.hovered || expanded ? 0.7 : 0.35
                    rotation: expanded ? 90 : 0
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.caption
                    Behavior on rotation { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                  }

                  Text {
                    id: timeLabel
                    anchors.left: chevron.right
                    anchors.leftMargin: Style.space(6)
                    anchors.verticalCenter: parent.verticalCenter
                    text: (index === 0 && !searchField.text.trim() ? "LATEST  ·  " : "") + root.stamp(modelData.ts)
                    color: root.bar.foreground
                    opacity: 0.5
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    font.letterSpacing: 0.8
                  }

                  PanelActionButton {
                    id: copyButton
                    radius: Style.space(8)
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    iconText: root.copiedId === modelData.id ? "󰄬" : "󰆏"
                    tooltipText: root.copiedId === modelData.id ? "Copied" : "Copy to clipboard"
                    foreground: root.copiedId === modelData.id ? Color.accent : root.bar.foreground
                    fontFamily: root.bar.fontFamily
                    onClicked: root.copy(index)
                  }
                }

                Text {
                  width: parent.width
                  readonly property bool highlighting: modelData.highlightedText !== undefined
                  text: highlighting
                    ? (expanded ? modelData.highlightedText : modelData.highlightedPreview)
                    : String(modelData.text || "")
                  textFormat: highlighting ? Text.RichText : Text.PlainText
                  color: root.bar.foreground
                  wrapMode: Text.Wrap
                  // Rich text cannot elide. Search supplies a short context
                  // preview instead, keeping the actual match in view.
                  maximumLineCount: expanded || highlighting ? 1000000 : 3
                  elide: expanded || highlighting ? Text.ElideNone : Text.ElideRight
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.body
                  lineHeight: 1.2
                }
              }
            }
          }

        }

        Item {
          id: footer
          width: parent.width
          implicitHeight: Math.max(searchField.implicitHeight, footerHint.implicitHeight, footerActions.implicitHeight)

          Flow {
            id: footerHint
            visible: !root.searchShown && !root.copiedId
            anchors.left: parent.left
            anchors.right: footerActions.left
            anchors.rightMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(12)
            KeyHint { keys: "↑ ↓"; label: "Select" }
            KeyHint { keys: "↵"; label: "Copy" }
            KeyHint { keys: "Esc"; label: "Close" }
          }

          Text {
            visible: !root.searchShown && !!root.copiedId
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "󰄬  Copied to clipboard"
            color: Color.accent
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
          }

          Controls.TextField {
            id: searchField
            visible: root.searchShown
            anchors.left: parent.left
            anchors.right: footerActions.left
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            placeholderText: "Search " + root.total + " saved dictations…"
            color: root.bar.foreground
            placeholderTextColor: Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.45)
            selectionColor: Color.accent
            selectedTextColor: Color.background
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.body
            padding: Style.space(8)
            rightPadding: searchCount.visible ? searchCount.implicitWidth + Style.space(18) : padding
            Text {
              id: searchCount
              anchors.right: parent.right
              anchors.rightMargin: Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              visible: searchField.text.trim().length > 0
              text: historyTimeout.running || searchTimer.running ? "Searching…"
                : root.resultsQuery !== searchField.text ? ""
                : root.matched + (root.matched === 1 ? " match" : " matches")
              color: root.bar.foreground
              opacity: 0.5
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.caption
            }
            background: Rectangle {
              radius: Style.space(8)
              color: Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.04)
              border.width: 1
              border.color: searchField.activeFocus ? Color.accent : "transparent"
            }
            onTextChanged: {
              root.copiedId = ""
              searchTimer.restart()
            }
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_F && (event.modifiers & Qt.ControlModifier)) {
                selectAll()
              } else if (event.key === Qt.Key_Escape) {
                root.escapeSearch()
              } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                root.moveSelection(event.key === Qt.Key_Down ? 1 : -1, 0)
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.copy(root.selectedIndex)
              } else if (event.key === Qt.Key_Tab) {
                keyCatcher.forceActiveFocus()
              } else return
              event.accepted = true
            }
          }

          Row {
            id: footerActions
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(4)

            PanelActionButton {
              anchors.verticalCenter: parent.verticalCenter
              radius: Style.space(8)
              iconText: "󰍉"
              fontSize: Style.font.iconLarge
              tooltipText: root.searchShown ? root.matched + " matching dictations" : "Just type to search · Ctrl+F"
              onClicked: root.search()
            }
            PanelActionButton {
              anchors.verticalCenter: parent.verticalCenter
              radius: Style.space(8)
              iconText: "󰑓"
              tooltipText: "Refresh history"
              enabled: !historyTimeout.running
              onClicked: root.refresh()
            }
            PanelActionButton {
              id: folderButton
              fontSize: Style.font.iconLarge * 1.35
              anchors.verticalCenter: parent.verticalCenter
              radius: Style.space(8)
              iconText: "󰉋"
              tooltipText: "Open transcript folder"
              enabled: !folderTimeout.running
              onClicked: {
                folderTimeout.restart()
                folderProc.running = true
              }
            }
          }
        }
      }
    }
  }
}

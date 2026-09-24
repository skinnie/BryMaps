import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import BryMaps

ApplicationWindow {
    id: win
    visible: true
    width: 1080
    height: 760
    minimumWidth: 820
    minimumHeight: 560
    title: qsTr("BryMaps")
    color: Theme.background

    property var allRegions: []
    property var selRegion: null
    property string outDir: ""
    property string lastDat: ""
    // navigation: stack of {id, name}; currentParent "" = world root
    property var navStack: []
    property var forwardStack: []
    property string currentParent: ""

    function regionCode(name) {
        var s = (name || "XX").replace(/[^A-Za-z]/g, "").toUpperCase()
        return "C" + (s.length >= 2 ? s.substring(0, 2) : "XX")
    }
    function humanSize(b) {
        if (!b) return ""
        if (b >= 1e9) return (b / 1e9).toFixed(1) + " GB"
        if (b >= 1e6) return Math.round(b / 1e6) + " MB"
        return Math.round(b / 1e3) + " kB"
    }
    function urlToPath(u) {
        var s = ("" + u).replace(/^file:\/\//, "")
        if (/^\/[A-Za-z]:/.test(s)) s = s.substring(1)
        return decodeURIComponent(s)
    }
    function destOrPrompt() {
        if (win.outDir) return win.outDir
        if (Backend.devicePath) return Backend.devicePath + "/MAP/Update"
        outDirDialog.open(); return ""
    }

    // search text mirrored as a property so the computed model binding tracks it
    property string searchText: ""

    Connections {
        target: Backend
        function onRegionsLoaded(list) { win.allRegions = list }
        function onLogLine(s) { logArea.text += s + "\n"; logArea.cursorPosition = logArea.length }
        function onProgress(v) { progress.indeterminate = (v < 0); if (v >= 0) progress.value = v }
        function onBuildFinished(ok, msg) {
            status.text = msg
            status.color = ok ? Theme.primary : Theme.error
            if (ok && msg.indexOf(".dat") >= 0) win.lastDat = msg
        }
    }

    // Declarative model: recomputed automatically whenever allRegions, currentParent or
    // searchText change. No imperative model assignment, so no timing race can blank it.
    readonly property var visibleRegions: {
        var all = win.allRegions
        var q = win.searchText.toLowerCase()
        var out = []
        if (q.length > 0) {
            for (var i = 0; i < all.length && out.length < 700; i++) {
                var r = all[i]
                if (r.name.toLowerCase().indexOf(q) >= 0 || (r.parent || "").toLowerCase().indexOf(q) >= 0)
                    out.push(r)
            }
        } else {
            for (var j = 0; j < all.length; j++)
                if (all[j].parent === win.currentParent) out.push(all[j])
        }
        return out
    }

    function drillInto(node) {
        win.navStack = win.navStack.concat([{ id: node.id, name: node.name }])
        win.currentParent = node.id
        win.forwardStack = []
        searchField.text = ""
    }
    function navTo(depth) {   // depth -1 = world root
        win.navStack = win.navStack.slice(0, depth + 1)
        win.currentParent = depth < 0 ? "" : win.navStack[depth].id
        win.forwardStack = []
        searchField.text = ""
    }
    function goBack() {
        if (win.navStack.length === 0) return
        var popped = win.navStack[win.navStack.length - 1]
        win.navStack = win.navStack.slice(0, -1)
        win.forwardStack = win.forwardStack.concat([popped])
        win.currentParent = win.navStack.length ? win.navStack[win.navStack.length - 1].id : ""
        searchField.text = ""
    }
    function goForward() {
        if (win.forwardStack.length === 0) return
        var node = win.forwardStack[win.forwardStack.length - 1]
        win.forwardStack = win.forwardStack.slice(0, -1)
        win.navStack = win.navStack.concat([node])
        win.currentParent = node.id
        searchField.text = ""
    }

    header: ToolBar {
        background: Rectangle { color: Theme.surface }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingLarge
            anchors.rightMargin: Theme.spacingLarge
            spacing: Theme.spacingMedium
            Text { text: "BryMaps"; color: Theme.text; font.pixelSize: Theme.fontSizeTitle; font.bold: true }
            Text {
                text: qsTr("Fresh OpenStreetMap maps for Bryton Aero 60 / Rider 450")
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
            }
            Item { Layout.fillWidth: true }
            Rectangle { width: 10; height: 10; radius: 5
                color: Backend.devicePath ? Theme.primary : Theme.error }
            Text {
                text: Backend.devicePath ? (Backend.deviceModel || qsTr("Bryton")) + qsTr(" connected")
                                         : qsTr("No device")
                color: Theme.text; font.pixelSize: Theme.fontSizeLabel
            }
            ToolButton {
                text: "⟳"
                ToolTip.visible: hovered; ToolTip.text: qsTr("Rescan for device")
                onClicked: Backend.refresh_device()
            }
            ToolButton {
                text: Theme.override === "light" ? "☀" : Theme.override === "dark" ? "☾" : "◐"
                font.pixelSize: Theme.fontSizeSubtitle
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Appearance: ") + (Theme.override === "light" ? qsTr("Light")
                              : Theme.override === "dark" ? qsTr("Dark") : qsTr("System"))
                onClicked: Theme.override = Theme.override === "system" ? "light"
                           : Theme.override === "light" ? "dark" : "system"
            }
        }
    }

    // Mouse back/forward buttons navigate the region tree. Only these two buttons are
    // accepted, so left-clicks, drags and the wheel pass straight through to the list below.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.BackButton | Qt.ForwardButton
        z: 10
        onPressed: (mouse) => {
            if (mouse.button === Qt.BackButton) win.goBack()
            else if (mouse.button === Qt.ForwardButton) win.goForward()
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLarge
        spacing: Theme.spacingLarge

        // ── region browser ──
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingMedium

            Text {
                text: qsTr("Choose a country or region")
                color: Theme.text; font.pixelSize: Theme.fontSizeLargeTitle; font.bold: true
            }
            Text {
                text: qsTr("Drill in: continent → country → region. Pick the smallest area that covers your rides — the device holds one file per area, so you never need a whole continent.")
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeLabel
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: qsTr("Search anywhere e.g. \"nord-pas\", \"switzerland\"…")
                onTextChanged: win.searchText = text
            }

            // breadcrumb (hidden while searching)
            Flow {
                Layout.fillWidth: true
                spacing: 4
                visible: searchField.text.length === 0
                Text {
                    text: "🌍 World"; color: Theme.primary; font.pixelSize: Theme.fontSizeLabel
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: win.navTo(-1) }
                }
                Repeater {
                    model: win.navStack
                    Row {
                        spacing: 4
                        Text { text: "›"; color: Theme.mutedText; font.pixelSize: Theme.fontSizeLabel }
                        Text {
                            text: modelData.name
                            color: index === win.navStack.length - 1 ? Theme.text : Theme.primary
                            font.pixelSize: Theme.fontSizeLabel
                            font.bold: index === win.navStack.length - 1
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: win.navTo(index) }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                // loading / empty state — so a blank list is never a mystery
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 2 * Theme.spacingLarge
                    horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                    visible: regionList.count === 0
                    color: Theme.mutedText; font.pixelSize: Theme.fontSizeLabel
                    text: win.allRegions.length === 0 ? qsTr("Loading region list…")
                          : win.searchText.length ? qsTr("No matches — try a different search.")
                          : qsTr("No sub-regions here. Use ‹ back or a breadcrumb above.")
                }
                ListView {
                    id: regionList
                    anchors.fill: parent; anchors.margins: Theme.spacingSmall
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    model: win.visibleRegions
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        width: regionList.width
                        height: 50
                        radius: Theme.radiusSmall
                        property bool selected: win.selRegion && win.selRegion.id === modelData.id
                        color: selected ? Theme.cardNested : (hover.hovered ? Theme.surface : "transparent")

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingSmall
                            spacing: Theme.spacingSmall
                            Column {
                                Layout.fillWidth: true
                                spacing: 2
                                Text { text: modelData.name; color: Theme.text; font.pixelSize: Theme.fontSizeBody }
                                Text {
                                    text: {
                                        var sz = win.humanSize(modelData.bytes) + qsTr(" download")
                                        if (searchField.text.length) return (modelData.parent || "") + " · " + sz
                                        return (modelData.hasChildren ? qsTr("double-click for zones · ") : "") + sz
                                    }
                                    color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                                }
                            }
                            Text {
                                visible: modelData.hasChildren && searchField.text.length === 0
                                text: "›"; color: Theme.mutedText; font.pixelSize: Theme.fontSizeTitle
                            }
                        }
                        HoverHandler { id: hover }
                        TapHandler {
                            acceptedButtons: Qt.LeftButton
                            onSingleTapped: win.selRegion = modelData
                            onDoubleTapped: {
                                win.selRegion = modelData
                                if (modelData.hasChildren && searchField.text.length === 0)
                                    win.drillInto(modelData)
                            }
                        }
                    }
                }
            }
        }

        // ── right: actions ──
        ColumnLayout {
            Layout.preferredWidth: 320
            Layout.fillHeight: true
            spacing: Theme.spacingMedium

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: selCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: selCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Selected"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        text: win.selRegion ? win.selRegion.name : qsTr("— nothing selected —")
                        color: win.selRegion ? Theme.text : Theme.mutedText
                        font.pixelSize: Theme.fontSizeSubtitle; font.bold: win.selRegion !== null
                    }
                    Text {
                        Layout.fillWidth: true; visible: win.selRegion !== null; wrapMode: Text.WordWrap
                        text: win.selRegion ? (win.selRegion.parent || "world") + " · " +
                              win.humanSize(win.selRegion.bytes) + qsTr(" OSM download") : ""
                        color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                    }
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        visible: win.selRegion !== null && win.selRegion.bytes > 3e9
                        text: qsTr("⚠ Large area — this is a multi-GB download and a long build. Prefer a country or region.")
                        color: Theme.warning; font.pixelSize: Theme.fontSizeCaption
                    }
                    Button {
                        Layout.fillWidth: true; Layout.topMargin: Theme.spacingSmall
                        text: qsTr("Build this map")
                        enabled: win.selRegion !== null && !Backend.busy
                        onClicked: {
                            var dest = win.destOrPrompt(); if (!dest) return
                            Backend.build_region(win.selRegion.id, dest, win.regionCode(win.selRegion.name))
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: devCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: devCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Device"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; elide: Text.ElideMiddle
                        text: Backend.devicePath || qsTr("Plug in the Bryton over USB")
                        color: Backend.devicePath ? Theme.text : Theme.mutedText
                        font.pixelSize: Theme.fontSizeCaption
                    }
                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Back up device maps to disk")
                        enabled: Backend.devicePath !== "" && !Backend.busy
                        onClicked: backupDialog.open()
                    }
                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Install last build to device")
                        enabled: win.lastDat !== "" && Backend.devicePath !== "" && !Backend.busy
                        onClicked: Backend.install_to_device(win.lastDat, "true")
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: outCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: outCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Output folder"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; elide: Text.ElideMiddle
                        text: win.outDir || (Backend.devicePath ? Backend.devicePath + "/MAP/Update  (device)"
                                                                 : qsTr("choose a folder"))
                        color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                    }
                    Button { Layout.fillWidth: true; text: qsTr("Change…"); onClicked: outDirDialog.open() }
                }
            }

            Item { Layout.fillHeight: true }

            ProgressBar { id: progress; Layout.fillWidth: true; from: 0; to: 1 }
            Text {
                id: status; Layout.fillWidth: true; wrapMode: Text.WordWrap
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                text: qsTr("Drill to a region and press Build.")
            }
        }
    }

    footer: Rectangle {
        color: Theme.surface
        implicitHeight: 130
        ScrollView {
            anchors.fill: parent; anchors.margins: Theme.spacingSmall
            TextArea {
                id: logArea
                readOnly: true; wrapMode: TextArea.Wrap
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption; font.family: "monospace"
                background: null
                text: qsTr("Ready.\n")
            }
        }
    }

    FolderDialog {
        id: outDirDialog
        title: qsTr("Choose output folder")
        onAccepted: win.outDir = win.urlToPath(selectedFolder)
    }
    FolderDialog {
        id: backupDialog
        title: qsTr("Choose backup destination")
        onAccepted: Backend.backup_device(win.urlToPath(selectedFolder))
    }
}

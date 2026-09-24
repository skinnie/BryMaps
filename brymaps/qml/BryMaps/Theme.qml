pragma Singleton
import QtQuick
import QtCore

// Palette and design tokens reused from the Sommet (ambit-app) desktop theme so BryMaps
// shares its visual identity: calm pine-green accent, stepped surfaces, hairline borders,
// no shadows, rounded corners. Trimmed to the tokens BryMaps actually uses.
QtObject {
    id: root

    property alias override: settingsId.themeOverride
    property Settings settingsObj: Settings {
        id: settingsId
        category: "appearance"
        property string themeOverride: "system"
    }

    readonly property bool isDark: {
        if (override === "light") return false
        if (override === "dark") return true
        return Qt.styleHints.colorScheme === Qt.Dark
    }

    readonly property color _lightBackground: "#E9EDF0"
    readonly property color _lightSurface: "#F2F5F7"
    readonly property color _lightCard: "#FFFFFF"
    readonly property color _lightCardNested: "#EDF1F4"
    readonly property color _lightBorder: "#DCE2E7"
    readonly property color _lightBorderStrong: "#C6CED6"
    readonly property color _lightPrimary: "#2E6A57"
    readonly property color _lightSecondary: "#5B6270"
    readonly property color _lightAccent: "#3C8571"
    readonly property color _lightWarning: "#9A7A22"
    readonly property color _lightError: "#B0473C"
    readonly property color _lightText: "#1A1D22"
    readonly property color _lightMutedText: "#5B6270"

    readonly property color _darkBackground: "#0F1216"
    readonly property color _darkSurface: "#171B22"
    readonly property color _darkCard: "#1B1F27"
    readonly property color _darkCardNested: "#232935"
    readonly property color _darkBorder: "#2B313C"
    readonly property color _darkBorderStrong: "#3A414E"
    readonly property color _darkPrimary: "#59A88C"
    readonly property color _darkSecondary: "#ADB6C2"
    readonly property color _darkAccent: "#7BC0A6"
    readonly property color _darkWarning: "#CB9A45"
    readonly property color _darkError: "#CE6A60"
    readonly property color _darkText: "#E9EBEE"
    readonly property color _darkMutedText: "#B4BDC9"

    readonly property color background: isDark ? _darkBackground : _lightBackground
    readonly property color surface: isDark ? _darkSurface : _lightSurface
    readonly property color card: isDark ? _darkCard : _lightCard
    readonly property color cardNested: isDark ? _darkCardNested : _lightCardNested
    readonly property color border: isDark ? _darkBorder : _lightBorder
    readonly property color borderStrong: isDark ? _darkBorderStrong : _lightBorderStrong
    readonly property color primary: isDark ? _darkPrimary : _lightPrimary
    readonly property color secondary: isDark ? _darkSecondary : _lightSecondary
    readonly property color accent: isDark ? _darkAccent : _lightAccent
    readonly property color warning: isDark ? _darkWarning : _lightWarning
    readonly property color error: isDark ? _darkError : _lightError
    readonly property color text: isDark ? _darkText : _lightText
    readonly property color mutedText: isDark ? _darkMutedText : _lightMutedText
    readonly property color mapAccent: _lightPrimary

    readonly property int radiusSmall: 8
    readonly property int radiusCard: 16
    readonly property int spacingSmall: 8
    readonly property int spacingMedium: 16
    readonly property int spacingLarge: 24

    readonly property int fontSizeTiny: 10
    readonly property int fontSizeCaption: 11
    readonly property int fontSizeLabel: 12
    readonly property int fontSizeBody: 13
    readonly property int fontSizeBodyLarge: 14
    readonly property int fontSizeSubtitle: 15
    readonly property int fontSizeHeading: 16
    readonly property int fontSizeTitle: 18
    readonly property int fontSizeLargeTitle: 20
    readonly property int fontSizeDisplay: 24
}

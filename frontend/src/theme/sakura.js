/**
 * 樱花柔 · Sakura Soft Design System
 * Naive UI 主题覆盖 —— 还原原有粉色/紫色/薄荷绿配色
 *
 * 设计令牌来源：templates/auth_admin.html :root 变量
 * 配色：樱花粉 #F06595 / 薰衣紫 #9B7DD4 / 薄荷绿 #3DD4A6
 * 字体：Nunito (正文) + Quicksand (标题/标签)
 * 效果：玻璃拟态 + 柔粉阴影 + 弹簧缓动
 */


// ── 樱花粉主题色 ──────────────────────────────────────────────
export const sakuraColors = {
  primary: '#F06595',
  primaryDark: '#D6336C',
  primaryLight: '#FF8FB1',
  primaryBg: '#FFF0F5',
  secondary: '#9B7DD4',
  secondaryDark: '#7B5BC4',
  secondaryLight: '#C9A0E8',
  secondaryBg: '#F5F0FA',
  accent: '#3DD4A6',
  accentDark: '#22B888',
  accentLight: '#5DEBBD',
  accentBg: '#EBFBF5',
  amber: '#F6A609',
  amberDark: '#D68910',
  amberBg: '#FFF9E6',
  danger: '#E64980',
  dangerBg: '#FFF0F6',
  bg: '#FDF6F0',
  surface: '#FFFFFF',
  muted: '#FBF2EE',
  muted2: '#F5E8E2',
  text: '#3D2B3C',
  text2: '#5C4555',
  text3: '#8B7588',
  text4: '#B0A0AD',
  border: '#F0DEE7',
  borderLight: '#F8E8EF',
  glassBg: 'rgba(255,255,255,.72)',
  glassBorder: 'rgba(255,255,255,.6)',
  scrollbarThumb: '#E8C5D4',
  scrollbarHover: '#D6336C',
}

// ── 渐变 ──────────────────────────────────────────────────────
export const sakuraGradients = {
  sakura: 'linear-gradient(135deg, #F06595, #FF8FB1)',
  spring: 'linear-gradient(135deg, #FF8FB1, #C9A0E8, #A8C5E8)',
  warm: 'linear-gradient(135deg, #FFF0F5, #F5F0FA)',
  lavender: 'linear-gradient(135deg, #9B7DD4, #C9A0E8)',
}

// ── 阴影 ──────────────────────────────────────────────────────
export const sakuraShadows = {
  sm: '0 1px 3px rgba(61,43,60,.04)',
  md: '0 4px 8px -2px rgba(240,101,149,.06), 0 2px 4px -1px rgba(61,43,60,.03)',
  lg: '0 8px 24px -6px rgba(240,101,149,.15), 0 2px 8px -2px rgba(61,43,60,.04)',
  xl: '0 16px 40px -8px rgba(240,101,149,.2), 0 4px 12px -4px rgba(61,43,60,.05)',
  pink: '0 8px 24px -6px rgba(240,101,149,.32)',
}

// ── 字体 ──────────────────────────────────────────────────────
const FONT_BODY = "'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
const FONT_DISPLAY = "'Quicksand', -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif"

/**
 * Naive UI 主题 overrides
 * 用樱花粉替换默认的蓝色主色调，还原 auth_admin.html 设计系统
 */
export const sakuraThemeOverrides = {
  common: {
    // ── 主色：樱花粉 ──
    primaryColor: sakuraColors.primary,
    primaryColorHover: sakuraColors.primaryLight,
    primaryColorPressed: sakuraColors.primaryDark,
    primaryColorSuppl: sakuraColors.primary,

    // ── Info：薰衣紫 ──
    infoColor: sakuraColors.secondary,
    infoColorHover: sakuraColors.secondaryLight,
    infoColorPressed: sakuraColors.secondaryDark,
    infoColorSuppl: sakuraColors.secondary,

    // ── Success：薄荷绿 ──
    successColor: sakuraColors.accent,
    successColorHover: sakuraColors.accentLight,
    successColorPressed: sakuraColors.accentDark,
    successColorSuppl: sakuraColors.accent,

    // ── Warning：琥珀橙 ──
    warningColor: sakuraColors.amber,
    warningColorHover: '#FFC04D',
    warningColorPressed: sakuraColors.amberDark,
    warningColorSuppl: sakuraColors.amber,

    // ── Error：玫瑰红 ──
    errorColor: sakuraColors.danger,
    errorColorHover: sakuraColors.primary,
    errorColorPressed: '#C2255C',
    errorColorSuppl: sakuraColors.danger,

    // ── 背景与表面 ──
    bodyColor: sakuraColors.bg,
    cardColor: sakuraColors.surface,
    modalColor: sakuraColors.surface,
    popoverColor: sakuraColors.surface,
    tableColor: sakuraColors.muted,
    tableHeaderColor: sakuraColors.muted,
    inputColor: sakuraColors.surface,
    inputColorDisabled: sakuraColors.muted,
    actionColor: sakuraColors.muted,
    hoveredColor: sakuraColors.primaryBg,

    // ── 文字 ──
    textColorBase: sakuraColors.text,
    textColor1: sakuraColors.text,
    textColor2: sakuraColors.text2,
    textColor3: sakuraColors.text3,
    textColorDisabled: sakuraColors.text4,
    placeholderColor: sakuraColors.text4,
    iconColor: sakuraColors.text3,
    iconColorHover: sakuraColors.primary,

    // ── 边框与分割 ──
    borderColor: sakuraColors.border,
    dividerColor: sakuraColors.borderLight,

    // ── 圆角（对应 --r-sm 10px）──
    borderRadius: '10px',
    borderRadiusSmall: '8px',

    // ── 字体 ──
    fontFamily: FONT_BODY,
    fontFamilyStrong: FONT_DISPLAY,
    fontSize: '14px',
    fontSizeMedium: '14px',
    fontSizeLarge: '15px',
    fontSizeHuge: '16px',
    fontWeight: '400',
    fontWeightStrong: '700',

    // ── 阴影 ──
    boxShadow1: sakuraShadows.sm,
    boxShadow2: sakuraShadows.md,
    boxShadow3: sakuraShadows.lg,

    // ── 过渡 ──
    durationFast: '0.2s',
    durationMedium: '0.28s',
    durationSlow: '0.3s',
    cubicBezierEaseInOut: 'cubic-bezier(.22,1,.36,1)',
    cubicBezierEaseOut: 'cubic-bezier(.22,1,.36,1)',
    cubicBezierEaseIn: 'cubic-bezier(.22,1,.36,1)',
  },

  // ── Button ──────────────────────────────────
  Button: {
    fontWeight: '700',
    fontWeightStrong: '700',
    borderRadiusTiny: '8px',
    borderRadiusSmall: '10px',
    borderRadiusMedium: '10px',
    borderRadiusLarge: '12px',
    borderRadiusRound: '999px',
    fontSizeTiny: '12px',
    fontSizeSmall: '13px',
    fontSizeMedium: '14px',
    fontSizeLarge: '15px',
    heightTiny: '26px',
    heightSmall: '32px',
    heightMedium: '38px',
    heightLarge: '44px',
    textColor: sakuraColors.text2,
    textColorHover: sakuraColors.primaryDark,
    textColorPressed: sakuraColors.primaryDark,
    textColorFocus: sakuraColors.primaryDark,
    color: sakuraColors.surface,
    colorHover: sakuraColors.primaryBg,
    colorPressed: sakuraColors.primaryBg,
    colorFocus: sakuraColors.primaryBg,
    border: `1px solid ${sakuraColors.border}`,
    borderHover: `1px solid ${sakuraColors.primaryLight}`,
    borderPressed: `1px solid ${sakuraColors.primary}`,
    borderFocus: `1px solid ${sakuraColors.primaryLight}`,
    textColorPrimary: '#FFFFFF',
    textColorHoverPrimary: '#FFFFFF',
    textColorPressedPrimary: '#FFFFFF',
    textColorFocusPrimary: '#FFFFFF',
  },

  // ── Card ────────────────────────────────────
  Card: {
    borderRadius: '20px',
    paddingMedium: '20px 24px',
    paddingLarge: '28px 32px',
    color: sakuraColors.surface,
    colorEmbedded: sakuraColors.muted,
    borderColor: sakuraColors.border,
    titleTextColor: sakuraColors.text,
    titleFontWeight: '700',
    closeColor: sakuraColors.text3,
    closeColorHover: sakuraColors.primary,
  },

  // ── Input ───────────────────────────────────
  Input: {
    borderRadius: '10px',
    border: `1px solid ${sakuraColors.border}`,
    borderHover: `1px solid ${sakuraColors.primaryLight}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    borderDisabled: `1px solid ${sakuraColors.borderLight}`,
    boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
    caretColor: sakuraColors.primary,
    color: sakuraColors.surface,
    colorDisabled: sakuraColors.muted,
    textColor: sakuraColors.text,
    placeholderColor: sakuraColors.text4,
    heightMedium: '38px',
    fontSizeMedium: '14px',
    groupLabelColor: sakuraColors.muted,
    groupLabelTextColor: sakuraColors.text2,
    groupLabelBorder: `1px solid ${sakuraColors.border}`,
  },

  // ── InputNumber ─────────────────────────────
  InputNumber: {
    borderRadius: '10px',
    borderHover: `1px solid ${sakuraColors.primaryLight}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
    heightMedium: '38px',
  },

  // ── Select ──────────────────────────────────
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: '10px',
        border: `1px solid ${sakuraColors.border}`,
        borderHover: `1px solid ${sakuraColors.primaryLight}`,
        borderActive: `1px solid ${sakuraColors.primary}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
        boxShadowActive: `0 0 0 3px ${sakuraColors.primaryBg}`,
        color: sakuraColors.surface,
        colorActive: sakuraColors.surface,
        textColor: sakuraColors.text,
        placeholderColor: sakuraColors.text4,
        heightMedium: '38px',
        fontSizeMedium: '14px',
      },
      InternalSelectMenu: {
        borderRadius: '12px',
        color: sakuraColors.surface,
        optionTextColor: sakuraColors.text2,
        optionTextColorActive: sakuraColors.primaryDark,
        optionColorActive: sakuraColors.primaryBg,
        optionColorPending: sakuraColors.muted,
        optionColorActivePending: sakuraColors.primaryBg,
        borderRadius: '12px',
      },
    },
  },

  // ── Tag / Badge ─────────────────────────────
  Tag: {
    borderRadius: '999px',
    heightMedium: '28px',
    heightSmall: '22px',
    fontSizeMedium: '12px',
    fontWeightStrong: '700',
  },

  // ── DataTable ───────────────────────────────
  DataTable: {
    borderRadius: '14px',
    borderColor: sakuraColors.borderLight,
    thColor: sakuraColors.muted,
    thColorHover: sakuraColors.primaryBg,
    thTextColor: sakuraColors.text4,
    thFontWeight: '700',
    tdColor: sakuraColors.surface,
    tdColorHover: sakuraColors.primaryBg,
    tdColorStriped: sakuraColors.muted,
    tdTextColor: sakuraColors.text2,
    fontSizeMedium: '13px',
    thPaddingMedium: '12px 16px',
    tdPaddingMedium: '12px 16px',
  },

  // ── Tabs ────────────────────────────────────
  Tabs: {
    tabTextColor: sakuraColors.text3,
    tabTextColorHover: sakuraColors.primaryLight,
    tabTextColorActive: sakuraColors.primaryDark,
    tabTextColorActiveHover: sakuraColors.primaryDark,
    tabTextColorActiveLine: sakuraColors.primary,
    tabTextColorHoverLine: sakuraColors.primaryLight,
    barColor: sakuraColors.primary,
    tabFontWeight: '700',
    tabPaddingMedium: '8px 16px',
    tabGapMedium: '4px',
  },

  // ── Switch / Toggle ─────────────────────────
  // 原始设计：开启状态使用薄荷绿 accent，而非主粉色
  Switch: {
    railColor: sakuraColors.muted2,
    railColorActive: sakuraColors.accent,
    railColorActiveHover: sakuraColors.accentLight,
    railColorActivePressed: sakuraColors.accentDark,
    buttonColor: '#FFFFFF',
    buttonColorActive: '#FFFFFF',
    boxShadow: '0 1px 3px rgba(0,0,0,.15)',
    boxShadowFocus: `0 0 0 3px ${sakuraColors.accentBg}`,
    loadingColor: sakuraColors.accent,
    heightMedium: '24px',
    widthMedium: '42px',
  },

  // ── Modal ───────────────────────────────────
  Modal: {
    borderRadius: '24px',
    color: sakuraColors.glassBg,
    titleTextColor: sakuraColors.text,
    titleFontWeight: '700',
    closeColor: sakuraColors.text3,
    closeColorHover: sakuraColors.primary,
    boxShadow: sakuraShadows.xl,
  },

  // ── Drawer ──────────────────────────────────
  Drawer: {
    borderRadius: '20px',
    color: sakuraColors.surface,
    headerBorderBottom: `1px solid ${sakuraColors.borderLight}`,
    titleTextColor: sakuraColors.text,
    titleFontWeight: '700',
  },

  // ── Form ────────────────────────────────────
  Form: {
    labelTextColor: sakuraColors.text2,
    labelFontWeight: '700',
    labelFontSizeMedium: '13px',
    labelFontSizeTopMedium: '13px',
    feedbackTextColorError: sakuraColors.danger,
    feedbackTextColorWarning: sakuraColors.amberDark,
  },

  // ── Checkbox ────────────────────────────────
  Checkbox: {
    borderRadius: '4px',
    colorChecked: sakuraColors.primary,
    colorCheckedHover: sakuraColors.primaryLight,
    colorCheckedPressed: sakuraColors.primaryDark,
    colorDisabled: sakuraColors.muted2,
    border: `1px solid ${sakuraColors.border}`,
    borderChecked: `1px solid ${sakuraColors.primary}`,
    borderHover: `1px solid ${sakuraColors.primaryLight}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
    checkMarkColor: '#FFFFFF',
    textColor: sakuraColors.text2,
    textColorHover: sakuraColors.primaryDark,
  },

  // ── Radio ───────────────────────────────────
  Radio: {
    buttonColorActive: sakuraColors.primary,
    buttonColorActiveHover: sakuraColors.primaryLight,
    buttonColorActivePressed: sakuraColors.primaryDark,
    buttonTextColorActive: '#FFFFFF',
    buttonTextColorActiveHover: '#FFFFFF',
    buttonTextColorHover: sakuraColors.primaryDark,
    dotColorActive: sakuraColors.primary,
    dotColorActiveHover: sakuraColors.primaryLight,
    boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
    textColor: sakuraColors.text2,
    textColorHover: sakuraColors.primaryDark,
  },

  // ── DatePicker ──────────────────────────────
  DatePicker: {
    panelBorderRadius: '14px',
    panelColor: sakuraColors.surface,
    panelHeaderDividerColor: sakuraColors.borderLight,
    calendarDaysBackgroundColorHover: sakuraColors.primaryBg,
    calendarDaysTextColor: sakuraColors.text2,
    itemTextColor: sakuraColors.text2,
    itemTextColorActive: '#FFFFFF',
    itemColorActive: sakuraColors.primary,
    itemColorHover: sakuraColors.primaryBg,
    itemColorActiveHover: sakuraColors.primaryLight,
    itemBorderRadius: '8px',
    arrowColor: sakuraColors.text3,
    peers: {
      Input: {
        borderRadius: '10px',
        borderHover: `1px solid ${sakuraColors.primaryLight}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
        heightMedium: '38px',
      },
    },
  },

  // ── Menu ─────────────────────────────────────
  Menu: {
    borderRadius: '10px',
    itemHeight: '44px',
    itemColorHover: sakuraColors.primaryBg,
    itemColorActive: sakuraColors.primaryBg,
    itemColorActiveHover: sakuraColors.primaryBg,
    itemColorActiveCollapsed: sakuraColors.primaryBg,
    itemTextColor: sakuraColors.text2,
    itemTextColorHover: sakuraColors.primaryDark,
    itemTextColorActive: sakuraColors.primaryDark,
    itemTextColorActiveHover: sakuraColors.primaryDark,
    itemTextColorChildActive: sakuraColors.primaryDark,
    itemTextColorChildActiveHover: sakuraColors.primaryDark,
    itemIconColor: sakuraColors.text3,
    itemIconColorHover: sakuraColors.primary,
    itemIconColorActive: sakuraColors.primary,
    itemIconColorActiveHover: sakuraColors.primary,
    itemIconColorChildActive: sakuraColors.primary,
    itemIconColorChildActiveHover: sakuraColors.primary,
    itemIconColorCollapsed: sakuraColors.text3,
    itemIconColorCollapsedHover: sakuraColors.primary,
    itemIconColorCollapsedActive: sakuraColors.primary,
    arrowColorActive: sakuraColors.primary,
    arrowColorChildActive: sakuraColors.primary,
    color: sakuraColors.surface,
  },

  // ── Layout ──────────────────────────────────
  Layout: {
    color: sakuraColors.surface,
    colorHover: sakuraColors.muted,
    siderColor: sakuraColors.surface,
    headerColor: sakuraColors.surface,
    bodyColor: sakuraColors.bg,
    headerBorderBottom: `1px solid ${sakuraColors.borderLight}`,
    textColor: sakuraColors.text2,
  },

  // ── Pagination ──────────────────────────────
  Pagination: {
    itemColorHover: sakuraColors.primaryBg,
    itemColorActive: sakuraColors.primary,
    itemColorActiveHover: sakuraColors.primaryLight,
    itemTextColorHover: sakuraColors.primaryDark,
    itemTextColorActive: '#FFFFFF',
    itemTextColorActiveHover: '#FFFFFF',
    itemBorder: `1px solid ${sakuraColors.border}`,
    itemBorderHover: `1px solid ${sakuraColors.primaryLight}`,
    itemBorderActive: `1px solid ${sakuraColors.primary}`,
    itemBorderRadius: '10px',
    buttonIconColor: sakuraColors.text3,
    buttonIconColorHover: sakuraColors.primary,
    buttonColorHover: sakuraColors.primaryBg,
  },

  // ── Avatar ──────────────────────────────────
  Avatar: {
    borderRadius: '10px',
    color: sakuraColors.primaryBg,
    textColor: sakuraColors.primaryDark,
  },

  // ── Progress ────────────────────────────────
  Progress: {
    fillColor: sakuraColors.primary,
    fillColorActive: sakuraColors.primaryLight,
    railColor: sakuraColors.muted2,
    textColor: sakuraColors.text3,
    fontSize: '12px',
  },

  // ── Spin ────────────────────────────────────
  Spin: {
    color: sakuraColors.primary,
    opacitySpinning: '1',
    textColor: sakuraColors.text3,
  },

  // ── Empty ───────────────────────────────────
  Empty: {
    textColor: sakuraColors.text4,
    iconColor: sakuraColors.text4,
    descriptionTextColor: sakuraColors.text4,
    fontSize: '14px',
  },

  // ── Divider ─────────────────────────────────
  Divider: {
    color: sakuraColors.borderLight,
    textColor: sakuraColors.text3,
    fontSize: '14px',
    titleFontWeight: '700',
    titleColor: sakuraColors.text2,
  },

  // ── Descriptions ───────────────────────────
  Descriptions: {
    borderRadius: '14px',
    color: sakuraColors.surface,
    borderedColor: sakuraColors.border,
    labelColor: sakuraColors.muted,
    labelTextColor: sakuraColors.text2,
    labelFontWeight: '700',
    contentTextColor: sakuraColors.text,
    thColor: sakuraColors.muted,
    thFontWeight: '700',
    thTextColor: sakuraColors.text2,
    tdColor: sakuraColors.surface,
    tdTextColor: sakuraColors.text2,
  },

  // ── Upload ──────────────────────────────────
  Upload: {
    draggerBorder: `1.5px dashed ${sakuraColors.border}`,
    draggerBorderHover: `1.5px dashed ${sakuraColors.primary}`,
    draggerBorderRadius: '20px',
    draggerColor: sakuraColors.muted,
    draggerColorHover: sakuraColors.primaryBg,
    itemColor: sakuraColors.surface,
    itemColorHover: sakuraColors.primaryBg,
    itemBorder: `1px solid ${sakuraColors.border}`,
    itemBorderHover: `1px solid ${sakuraColors.primaryLight}`,
    itemBorderRadius: '10px',
  },

  // ── Steps ──────────────────────────────────
  Steps: {
    indicatorTextColorProcess: '#FFFFFF',
    indicatorTextColorFinish: '#FFFFFF',
    indicatorColorProcess: sakuraColors.primary,
    indicatorColorFinish: sakuraColors.accent,
    indicatorBorderColorProcess: sakuraColors.primary,
    indicatorBorderColorFinish: sakuraColors.accent,
    indicatorBorderRadius: '999px',
    splitColor: sakuraColors.border,
    titleTextColor: sakuraColors.text2,
    titleTextColorActive: sakuraColors.primaryDark,
    titleFontWeightActive: '700',
    descriptionTextColor: sakuraColors.text3,
  },

  // ── Message ─────────────────────────────────
  Message: {
    borderRadius: '12px',
    padding: '10px 16px',
    boxShadow: sakuraShadows.lg,
  },

  // ── Notification ────────────────────────────
  Notification: {
    borderRadius: '16px',
    boxShadow: sakuraShadows.xl,
    padding: '16px 20px',
    titleTextColor: sakuraColors.text,
    titleFontWeight: '700',
    textColor: sakuraColors.text2,
    descriptionTextColor: sakuraColors.text3,
  },

  // ── Dialog ──────────────────────────────────
  Dialog: {
    borderRadius: '20px',
    titleTextColor: sakuraColors.text,
    titleFontWeight: '700',
    textColor: sakuraColors.text2,
    iconColor: sakuraColors.primary,
  },

  // ── Tooltip ─────────────────────────────────
  Tooltip: {
    borderRadius: '8px',
    padding: '6px 12px',
    color: sakuraColors.text,
    textColor: '#FFFFFF',
    boxShadow: sakuraShadows.md,
  },

  // ── Popover ────────────────────────────────
  Popover: {
    borderRadius: '14px',
    padding: '16px 20px',
    color: sakuraColors.surface,
    textColor: sakuraColors.text2,
    boxShadow: sakuraShadows.lg,
  },

  // ── Dropdown ────────────────────────────────
  Dropdown: {
    borderRadius: '12px',
    color: sakuraColors.surface,
    optionColorHover: sakuraColors.primaryBg,
    optionColorActive: sakuraColors.primaryBg,
    optionTextColor: sakuraColors.text2,
    optionTextColorHover: sakuraColors.primaryDark,
    optionTextColorActive: sakuraColors.primaryDark,
    optionIconColorHover: sakuraColors.primary,
    boxShadow: sakuraShadows.lg,
  },

  // ── DynamicTags ─────────────────────────────
  DynamicTags: {
    peers: {
      Input: {
        borderRadius: '10px',
        borderHover: `1px solid ${sakuraColors.primaryLight}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${sakuraColors.primaryBg}`,
        heightMedium: '28px',
      },
      Tag: {
        borderRadius: '999px',
        heightMedium: '26px',
      },
      Button: {
        color: sakuraColors.primaryBg,
        colorHover: sakuraColors.primaryLight,
        border: `1px solid ${sakuraColors.border}`,
        borderHover: `1px solid ${sakuraColors.primaryLight}`,
        textColor: sakuraColors.primaryDark,
        textColorHover: sakuraColors.primaryDark,
        borderRadius: '999px',
      },
    },
  },

  // ── LoadingBar ──────────────────────────────
  LoadingBar: {
    colorLoading: sakuraColors.primary,
    height: '3px',
    borderRadius: '999px',
  },

  // ── Skeleton ───────────────────────────────
  Skeleton: {
    color: sakuraColors.muted,
    colorEnd: sakuraColors.primaryBg,
    borderRadius: '10px',
  },

  // ── BackTop ────────────────────────────────
  BackTop: {
    borderRadius: '999px',
    color: sakuraColors.primary,
    colorHover: sakuraColors.primaryLight,
    textColor: '#FFFFFF',
    boxShadow: sakuraShadows.md,
  },

  // ── Badge ───────────────────────────────────
  Badge: {
    color: sakuraColors.danger,
    colorError: sakuraColors.danger,
    colorSuccess: sakuraColors.accent,
    colorWarning: sakuraColors.amber,
    colorInfo: sakuraColors.secondary,
    textColor: '#FFFFFF',
    borderRadius: '999px',
  },

  // ── Grid ───────────────────────────────────
  Grid: {
    colorHover: sakuraColors.primaryBg,
  },

  // ── Space ──────────────────────────────────
  // (uses common defaults, no specific overrides needed)
}

// ── 深色主题覆盖 ──────────────────────────────────────────────
// 暗色配色：深紫底 #1A1320 + 樱花粉点缀，保持与亮色主题一致的视觉语言
const darkPalette = {
  bg: '#1A1320',           // 最深背景
  surface: '#221825',      // 表面 / 输入 / 弹层
  card: '#261A28',         // 卡片
  elevated: '#2D2028',     // 抬升表面（表头 / 操作栏）
  hover: '#332530',         // 悬停
  active: '#3D2B3C',        // 激活 / 边框
  text: '#F5E8EF',          // 主文字
  text2: '#D4BFCB',        // 次文字
  text3: '#9B7D92',         // 三级文字
  textDisabled: '#5C4555',  // 禁用文字
  border: '#3D2B3C',        // 默认边框
  borderLight: '#332530',   // 次级边框 / 分割
  primaryBg: 'rgba(240,101,149,.15)', // 粉色聚焦光晕
  glassBg: 'rgba(38,26,40,.72)',
  glassBorder: 'rgba(61,43,60,.5)',
}

export const sakuraDarkThemeOverrides = {
  common: {
    // ── 主色：樱花粉（hover 偏深、pressed 偏亮，适配暗色背景）──
    primaryColor: sakuraColors.primary,
    primaryColorHover: sakuraColors.primaryDark,
    primaryColorPressed: sakuraColors.primaryLight,
    primaryColorSuppl: sakuraColors.primary,

    // ── Info：薰衣紫 ──
    infoColor: sakuraColors.secondary,
    infoColorHover: sakuraColors.secondaryDark,
    infoColorPressed: sakuraColors.secondaryLight,
    infoColorSuppl: sakuraColors.secondary,

    // ── Success：薄荷绿 ──
    successColor: sakuraColors.accent,
    successColorHover: sakuraColors.accentDark,
    successColorPressed: sakuraColors.accentLight,
    successColorSuppl: sakuraColors.accent,

    // ── Warning：琥珀橙 ──
    warningColor: sakuraColors.amber,
    warningColorHover: sakuraColors.amberDark,
    warningColorPressed: '#FFC04D',
    warningColorSuppl: sakuraColors.amber,

    // ── Error：玫瑰红 ──
    errorColor: sakuraColors.danger,
    errorColorHover: '#C2255C',
    errorColorPressed: sakuraColors.primary,
    errorColorSuppl: sakuraColors.danger,

    // ── 背景与表面 ──
    bodyColor: darkPalette.bg,
    cardColor: darkPalette.card,
    modalColor: darkPalette.card,
    popoverColor: darkPalette.surface,
    tableColor: darkPalette.surface,
    tableHeaderColor: darkPalette.elevated,
    inputColor: darkPalette.surface,
    inputColorDisabled: darkPalette.bg,
    actionColor: darkPalette.elevated,
    hoveredColor: darkPalette.active,

    // ── 文字 ──
    textColorBase: darkPalette.text,
    textColor1: darkPalette.text,
    textColor2: darkPalette.text2,
    textColor3: darkPalette.text3,
    textColorDisabled: darkPalette.textDisabled,
    placeholderColor: darkPalette.textDisabled,
    iconColor: darkPalette.text3,
    iconColorHover: sakuraColors.primary,

    // ── 边框与分割 ──
    borderColor: darkPalette.border,
    dividerColor: darkPalette.borderLight,

    // ── 圆角（对应 --r-sm 10px）──
    borderRadius: '10px',
    borderRadiusSmall: '8px',

    // ── 字体 ──
    fontFamily: FONT_BODY,
    fontFamilyStrong: FONT_DISPLAY,
    fontSize: '14px',
    fontSizeMedium: '14px',
    fontSizeLarge: '15px',
    fontSizeHuge: '16px',
    fontWeight: '400',
    fontWeightStrong: '700',

    // ── 阴影 ──
    boxShadow1: sakuraShadows.sm,
    boxShadow2: sakuraShadows.md,
    boxShadow3: sakuraShadows.lg,

    // ── 过渡 ──
    durationFast: '0.2s',
    durationMedium: '0.28s',
    durationSlow: '0.3s',
    cubicBezierEaseInOut: 'cubic-bezier(.22,1,.36,1)',
    cubicBezierEaseOut: 'cubic-bezier(.22,1,.36,1)',
    cubicBezierEaseIn: 'cubic-bezier(.22,1,.36,1)',
  },

  // ── Button ──────────────────────────────────
  Button: {
    fontWeight: '700',
    fontWeightStrong: '700',
    borderRadiusTiny: '8px',
    borderRadiusSmall: '10px',
    borderRadiusMedium: '10px',
    borderRadiusLarge: '12px',
    borderRadiusRound: '999px',
    fontSizeTiny: '12px',
    fontSizeSmall: '13px',
    fontSizeMedium: '14px',
    fontSizeLarge: '15px',
    heightTiny: '26px',
    heightSmall: '32px',
    heightMedium: '38px',
    heightLarge: '44px',
    textColor: darkPalette.text2,
    textColorHover: sakuraColors.primaryLight,
    textColorPressed: sakuraColors.primaryDark,
    textColorFocus: sakuraColors.primaryLight,
    color: darkPalette.card,
    colorHover: darkPalette.hover,
    colorPressed: darkPalette.elevated,
    colorFocus: darkPalette.hover,
    border: `1px solid ${darkPalette.border}`,
    borderHover: `1px solid ${sakuraColors.primary}`,
    borderPressed: `1px solid ${sakuraColors.primaryDark}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    textColorPrimary: '#FFFFFF',
    textColorHoverPrimary: '#FFFFFF',
    textColorPressedPrimary: '#FFFFFF',
    textColorFocusPrimary: '#FFFFFF',
  },

  // ── Card ────────────────────────────────────
  Card: {
    borderRadius: '20px',
    paddingMedium: '20px 24px',
    paddingLarge: '28px 32px',
    color: darkPalette.card,
    colorEmbedded: darkPalette.surface,
    colorModal: darkPalette.surface,
    borderColor: darkPalette.border,
    titleTextColor: darkPalette.text,
    titleFontWeight: '700',
    closeColor: darkPalette.text3,
    closeColorHover: sakuraColors.primary,
  },

  // ── Input ───────────────────────────────────
  Input: {
    borderRadius: '10px',
    border: `1px solid ${darkPalette.border}`,
    borderHover: `1px solid ${sakuraColors.primary}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    borderDisabled: `1px solid ${darkPalette.borderLight}`,
    boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
    caretColor: sakuraColors.primary,
    color: darkPalette.surface,
    colorFocus: darkPalette.elevated,
    colorDisabled: darkPalette.bg,
    textColor: darkPalette.text,
    placeholderColor: darkPalette.textDisabled,
    heightMedium: '38px',
    fontSizeMedium: '14px',
    groupLabelColor: darkPalette.elevated,
    groupLabelTextColor: darkPalette.text2,
    groupLabelBorder: `1px solid ${darkPalette.border}`,
  },

  // ── InputNumber ─────────────────────────────
  InputNumber: {
    borderRadius: '10px',
    borderHover: `1px solid ${sakuraColors.primary}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
    heightMedium: '38px',
  },

  // ── Select ──────────────────────────────────
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: '10px',
        border: `1px solid ${darkPalette.border}`,
        borderHover: `1px solid ${sakuraColors.primary}`,
        borderActive: `1px solid ${sakuraColors.primary}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
        boxShadowActive: `0 0 0 3px ${darkPalette.primaryBg}`,
        color: darkPalette.surface,
        colorActive: darkPalette.elevated,
        textColor: darkPalette.text,
        placeholderColor: darkPalette.textDisabled,
        heightMedium: '38px',
        fontSizeMedium: '14px',
      },
      InternalSelectMenu: {
        borderRadius: '12px',
        color: darkPalette.surface,
        optionTextColor: darkPalette.text2,
        optionTextColorActive: sakuraColors.primaryLight,
        optionColorActive: darkPalette.active,
        optionColorPending: darkPalette.hover,
        optionColorActivePending: darkPalette.active,
        borderRadius: '12px',
      },
    },
  },

  // ── Tag ─────────────────────────────────────
  Tag: {
    borderRadius: '999px',
    heightMedium: '28px',
    heightSmall: '22px',
    fontSizeMedium: '12px',
    fontWeightStrong: '700',
    color: darkPalette.active,
    colorPrimary: darkPalette.active,
    colorInfo: darkPalette.active,
    colorSuccess: darkPalette.active,
    colorWarning: darkPalette.active,
    colorError: darkPalette.active,
    textColor: darkPalette.text2,
  },

  // ── DataTable ───────────────────────────────
  DataTable: {
    borderRadius: '14px',
    borderColor: darkPalette.border,
    thColor: darkPalette.elevated,
    thColorHover: darkPalette.hover,
    thTextColor: darkPalette.text2,
    thFontWeight: '700',
    tdColor: darkPalette.card,
    tdColorHover: darkPalette.hover,
    tdColorStriped: darkPalette.surface,
    tdTextColor: darkPalette.text2,
    fontSizeMedium: '13px',
    thPaddingMedium: '12px 16px',
    tdPaddingMedium: '12px 16px',
  },

  // ── Tabs ────────────────────────────────────
  Tabs: {
    tabTextColor: darkPalette.text2,
    tabTextColorHover: sakuraColors.primaryLight,
    tabTextColorActive: sakuraColors.primary,
    tabTextColorActiveHover: sakuraColors.primaryLight,
    tabTextColorActiveLine: sakuraColors.primary,
    tabTextColorHoverLine: sakuraColors.primaryLight,
    barColor: sakuraColors.primary,
    tabFontWeight: '700',
    tabPaddingMedium: '8px 16px',
    tabGapMedium: '4px',
  },

  // ── Switch / Toggle ─────────────────────────
  // 原始设计：开启状态使用薄荷绿 accent，而非主粉色
  Switch: {
    railColor: darkPalette.border,
    railColorActive: sakuraColors.accent,
    railColorActiveHover: sakuraColors.accentLight,
    railColorActivePressed: sakuraColors.accentDark,
    buttonColor: '#FFFFFF',
    buttonColorActive: '#FFFFFF',
    boxShadow: '0 1px 3px rgba(0,0,0,.3)',
    boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
    loadingColor: sakuraColors.accent,
    heightMedium: '24px',
    widthMedium: '42px',
  },

  // ── Modal ───────────────────────────────────
  Modal: {
    borderRadius: '24px',
    color: darkPalette.glassBg,
    titleTextColor: darkPalette.text,
    titleFontWeight: '700',
    closeColor: darkPalette.text3,
    closeColorHover: sakuraColors.primary,
    boxShadow: sakuraShadows.xl,
  },

  // ── Drawer ──────────────────────────────────
  Drawer: {
    borderRadius: '20px',
    color: darkPalette.surface,
    headerBorderBottom: `1px solid ${darkPalette.borderLight}`,
    titleTextColor: darkPalette.text,
    titleFontWeight: '700',
  },

  // ── Form ────────────────────────────────────
  Form: {
    labelTextColor: darkPalette.text2,
    labelFontWeight: '700',
    labelFontSizeMedium: '13px',
    labelFontSizeTopMedium: '13px',
    feedbackTextColorError: sakuraColors.danger,
    feedbackTextColorWarning: sakuraColors.amberDark,
  },

  // ── Checkbox ────────────────────────────────
  Checkbox: {
    borderRadius: '4px',
    colorChecked: sakuraColors.primary,
    colorCheckedHover: sakuraColors.primaryLight,
    colorCheckedPressed: sakuraColors.primaryDark,
    colorDisabled: darkPalette.border,
    border: `1px solid ${darkPalette.border}`,
    borderChecked: `1px solid ${sakuraColors.primary}`,
    borderHover: `1px solid ${sakuraColors.primary}`,
    borderFocus: `1px solid ${sakuraColors.primary}`,
    boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
    checkMarkColor: '#FFFFFF',
    textColor: darkPalette.text2,
    textColorHover: sakuraColors.primaryLight,
  },

  // ── Radio ───────────────────────────────────
  Radio: {
    buttonColorActive: sakuraColors.primary,
    buttonColorActiveHover: sakuraColors.primaryLight,
    buttonColorActivePressed: sakuraColors.primaryDark,
    buttonTextColorActive: '#FFFFFF',
    buttonTextColorActiveHover: '#FFFFFF',
    buttonTextColorHover: sakuraColors.primaryLight,
    dotColorActive: sakuraColors.primary,
    dotColorActiveHover: sakuraColors.primaryLight,
    boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
    textColor: darkPalette.text2,
    textColorHover: sakuraColors.primaryLight,
  },

  // ── DatePicker ──────────────────────────────
  DatePicker: {
    panelBorderRadius: '14px',
    panelColor: darkPalette.surface,
    panelHeaderDividerColor: darkPalette.borderLight,
    calendarDaysBackgroundColorHover: darkPalette.active,
    calendarDaysTextColor: darkPalette.text2,
    itemTextColor: darkPalette.text2,
    itemTextColorActive: '#FFFFFF',
    itemColorActive: sakuraColors.primary,
    itemColorHover: darkPalette.active,
    itemColorActiveHover: sakuraColors.primaryLight,
    itemBorderRadius: '8px',
    arrowColor: darkPalette.text3,
    peers: {
      Input: {
        borderRadius: '10px',
        borderHover: `1px solid ${sakuraColors.primary}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
        heightMedium: '38px',
      },
    },
  },

  // ── Menu ─────────────────────────────────────
  Menu: {
    borderRadius: '10px',
    itemHeight: '44px',
    itemColorHover: darkPalette.hover,
    itemColorActive: darkPalette.active,
    itemColorActiveHover: darkPalette.active,
    itemColorActiveCollapsed: darkPalette.active,
    itemTextColor: darkPalette.text2,
    itemTextColorHover: sakuraColors.primary,
    itemTextColorActive: sakuraColors.primary,
    itemTextColorActiveHover: sakuraColors.primary,
    itemTextColorChildActive: sakuraColors.primary,
    itemTextColorChildActiveHover: sakuraColors.primary,
    itemIconColor: darkPalette.text3,
    itemIconColorHover: sakuraColors.primary,
    itemIconColorActive: sakuraColors.primary,
    itemIconColorActiveHover: sakuraColors.primary,
    itemIconColorChildActive: sakuraColors.primary,
    itemIconColorChildActiveHover: sakuraColors.primary,
    itemIconColorCollapsed: darkPalette.text3,
    itemIconColorCollapsedHover: sakuraColors.primary,
    itemIconColorCollapsedActive: sakuraColors.primary,
    arrowColorActive: sakuraColors.primary,
    arrowColorChildActive: sakuraColors.primary,
    color: darkPalette.surface,
  },

  // ── Layout ──────────────────────────────────
  Layout: {
    color: darkPalette.bg,
    colorHover: darkPalette.surface,
    siderColor: darkPalette.surface,
    headerColor: darkPalette.surface,
    bodyColor: darkPalette.bg,
    headerBorderBottom: `1px solid ${darkPalette.borderLight}`,
    textColor: darkPalette.text2,
  },

  // ── Pagination ──────────────────────────────
  Pagination: {
    itemColorHover: darkPalette.active,
    itemColorActive: sakuraColors.primary,
    itemColorActiveHover: sakuraColors.primaryLight,
    itemTextColor: darkPalette.text2,
    itemTextColorHover: sakuraColors.primaryLight,
    itemTextColorActive: '#FFFFFF',
    itemTextColorActiveHover: '#FFFFFF',
    itemBorder: `1px solid ${darkPalette.border}`,
    itemBorderHover: `1px solid ${sakuraColors.primary}`,
    itemBorderActive: `1px solid ${sakuraColors.primary}`,
    itemBorderRadius: '10px',
    buttonIconColor: darkPalette.text3,
    buttonIconColorHover: sakuraColors.primary,
    buttonColorHover: darkPalette.active,
  },

  // ── Avatar ──────────────────────────────────
  Avatar: {
    borderRadius: '10px',
    color: darkPalette.active,
    textColor: sakuraColors.primaryLight,
  },

  // ── Progress ────────────────────────────────
  Progress: {
    fillColor: sakuraColors.primary,
    fillColorActive: sakuraColors.primaryLight,
    railColor: darkPalette.borderLight,
    textColor: darkPalette.text3,
    fontSize: '12px',
  },

  // ── Spin ────────────────────────────────────
  Spin: {
    color: sakuraColors.primary,
    opacitySpinning: '1',
    textColor: darkPalette.text3,
  },

  // ── Empty ───────────────────────────────────
  Empty: {
    textColor: darkPalette.textDisabled,
    iconColor: darkPalette.textDisabled,
    descriptionTextColor: darkPalette.textDisabled,
    fontSize: '14px',
  },

  // ── Divider ─────────────────────────────────
  Divider: {
    color: darkPalette.borderLight,
    textColor: darkPalette.text3,
    fontSize: '14px',
    titleFontWeight: '700',
    titleColor: darkPalette.text2,
  },

  // ── Descriptions ───────────────────────────
  Descriptions: {
    borderRadius: '14px',
    color: darkPalette.card,
    borderedColor: darkPalette.border,
    labelColor: darkPalette.elevated,
    labelTextColor: darkPalette.text2,
    labelFontWeight: '700',
    contentTextColor: darkPalette.text,
    thColor: darkPalette.elevated,
    thFontWeight: '700',
    thTextColor: darkPalette.text2,
    tdColor: darkPalette.card,
    tdTextColor: darkPalette.text2,
  },

  // ── Upload ──────────────────────────────────
  Upload: {
    draggerBorder: `1.5px dashed ${darkPalette.border}`,
    draggerBorderHover: `1.5px dashed ${sakuraColors.primary}`,
    draggerBorderRadius: '20px',
    draggerColor: darkPalette.elevated,
    draggerColorHover: darkPalette.active,
    itemColor: darkPalette.card,
    itemColorHover: darkPalette.hover,
    itemBorder: `1px solid ${darkPalette.border}`,
    itemBorderHover: `1px solid ${sakuraColors.primary}`,
    itemBorderRadius: '10px',
  },

  // ── Steps ──────────────────────────────────
  Steps: {
    indicatorTextColorProcess: '#FFFFFF',
    indicatorTextColorFinish: '#FFFFFF',
    indicatorColorProcess: sakuraColors.primary,
    indicatorColorFinish: sakuraColors.accent,
    indicatorBorderColorProcess: sakuraColors.primary,
    indicatorBorderColorFinish: sakuraColors.accent,
    indicatorBorderRadius: '999px',
    splitColor: darkPalette.border,
    titleTextColor: darkPalette.text2,
    titleTextColorActive: sakuraColors.primaryLight,
    titleFontWeightActive: '700',
    descriptionTextColor: darkPalette.text3,
  },

  // ── Message ─────────────────────────────────
  Message: {
    borderRadius: '12px',
    padding: '10px 16px',
    color: darkPalette.elevated,
    boxShadow: sakuraShadows.lg,
  },

  // ── Notification ────────────────────────────
  Notification: {
    borderRadius: '16px',
    boxShadow: sakuraShadows.xl,
    padding: '16px 20px',
    color: darkPalette.elevated,
    titleTextColor: darkPalette.text,
    titleFontWeight: '700',
    textColor: darkPalette.text2,
    descriptionTextColor: darkPalette.text3,
  },

  // ── Dialog ──────────────────────────────────
  Dialog: {
    borderRadius: '20px',
    color: darkPalette.card,
    titleTextColor: darkPalette.text,
    titleFontWeight: '700',
    textColor: darkPalette.text2,
    iconColor: sakuraColors.primary,
  },

  // ── Tooltip ─────────────────────────────────
  Tooltip: {
    borderRadius: '8px',
    padding: '6px 12px',
    color: darkPalette.active,
    textColor: darkPalette.text,
    boxShadow: sakuraShadows.md,
  },

  // ── Popover ────────────────────────────────
  Popover: {
    borderRadius: '14px',
    padding: '16px 20px',
    color: darkPalette.surface,
    textColor: darkPalette.text2,
    boxShadow: sakuraShadows.lg,
  },

  // ── Dropdown ────────────────────────────────
  Dropdown: {
    borderRadius: '12px',
    color: darkPalette.card,
    optionColorHover: darkPalette.active,
    optionColorActive: darkPalette.active,
    optionTextColor: darkPalette.text2,
    optionTextColorHover: sakuraColors.primaryLight,
    optionTextColorActive: sakuraColors.primaryLight,
    optionIconColorHover: sakuraColors.primary,
    boxShadow: sakuraShadows.lg,
  },

  // ── DynamicTags ─────────────────────────────
  DynamicTags: {
    peers: {
      Input: {
        borderRadius: '10px',
        borderHover: `1px solid ${sakuraColors.primary}`,
        borderFocus: `1px solid ${sakuraColors.primary}`,
        boxShadowFocus: `0 0 0 3px ${darkPalette.primaryBg}`,
        heightMedium: '28px',
      },
      Tag: {
        borderRadius: '999px',
        heightMedium: '26px',
      },
      Button: {
        color: darkPalette.active,
        colorHover: sakuraColors.primaryDark,
        border: `1px solid ${darkPalette.border}`,
        borderHover: `1px solid ${sakuraColors.primary}`,
        textColor: sakuraColors.primaryLight,
        textColorHover: darkPalette.text,
        borderRadius: '999px',
      },
    },
  },

  // ── LoadingBar ──────────────────────────────
  LoadingBar: {
    colorLoading: sakuraColors.primary,
    height: '3px',
    borderRadius: '999px',
  },

  // ── Skeleton ───────────────────────────────
  Skeleton: {
    color: darkPalette.elevated,
    colorEnd: darkPalette.hover,
    borderRadius: '10px',
  },

  // ── BackTop ────────────────────────────────
  BackTop: {
    borderRadius: '999px',
    color: sakuraColors.primary,
    colorHover: sakuraColors.primaryLight,
    textColor: '#FFFFFF',
    boxShadow: sakuraShadows.md,
  },

  // ── Badge ───────────────────────────────────
  Badge: {
    color: sakuraColors.danger,
    colorError: sakuraColors.danger,
    colorSuccess: sakuraColors.accent,
    colorWarning: sakuraColors.amber,
    colorInfo: sakuraColors.secondary,
    textColor: '#FFFFFF',
    borderRadius: '999px',
  },

  // ── Grid ───────────────────────────────────
  Grid: {
    colorHover: darkPalette.hover,
  },

  // ── Space ──────────────────────────────────
  // (uses common defaults, no specific overrides needed)
}

// ── 深色 CSS 变量 ─────────────────────────────────────────────
export const darkCssVars = {
  '--bg': '#1A1320',
  '--surface': '#261A28',
  '--card-bg': '#261A28',
  '--muted': '#2D2028',
  '--muted-2': '#332530',
  '--text': '#F5E8EF',
  '--text-2': '#D4BFCB',
  '--text-3': '#9B7D92',
  '--text-4': '#5C4555',
  '--border': '#3D2B3C',
  '--border-l': '#332530',
  '--primary-bg': 'rgba(240,101,149,.12)',
  '--secondary-bg': 'rgba(155,125,212,.12)',
  '--accent-bg': 'rgba(61,212,166,.12)',
  '--amber-bg': 'rgba(246,166,9,.12)',
  '--danger-bg': 'rgba(230,73,128,.12)',
  '--glass-bg': 'rgba(38,26,40,.72)',
  '--glass-border': 'rgba(61,43,60,.5)',
}

const MAIN_TAB_LABELS = {
  today: 'Today',
  profile: 'My Profile',
  menu: 'Menu Builder',
  services: 'Services',
  payments: 'Payment Links',
  orders: 'Orders',
  clients: 'Clients',
  prep: 'Prep Planning',
  messages: 'Messages',
  dashboard: 'Dashboard',
  metrics: 'Metrics'
}

const MENU_SUBTAB_LABELS = {
  ingredients: 'Ingredients',
  dishes: 'Dishes',
  meals: 'Meals'
}

const SERVICES_SUBTAB_LABELS = {
  services: 'Services',
  'meal-shares': 'Meal Shares'
}

const PROFILE_SUBTAB_LABELS = {
  info: 'My Profile',
  photos: 'Photos'
}

const TAB_ALIASES = {
  'menu-builder': 'menu',
  kitchen: 'menu',
  'payment-links': 'payments',
  paymentlinks: 'payments',
  payment: 'payments',
  service: 'services',
  offerings: 'services',
  offering: 'services',
  'prep-planning': 'prep',
  'prep-plans': 'prep',
  'my-profile': 'profile'
}

function normalizeKey(value) {
  if (!value) return ''
  return String(value).trim().toLowerCase().replace(/_/g, '-').replace(/\s+/g, '-')
}

function formatLabel(value) {
  if (!value) return ''
  return String(value)
    .replace(/_/g, '-')
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function normalizeMealShares(value) {
  const key = normalizeKey(value)
  if (!key) return null
  if (['meal-shares', 'mealshare', 'mealshares', 'meal-share'].includes(key)) return 'meal-shares'
  if (['event', 'events'].includes(key)) return 'meal-shares'
  return null
}

function menuSubTabFromKey(value) {
  const key = normalizeKey(value)
  if (!key) return null
  if (['ingredient', 'ingredients'].includes(key)) return 'ingredients'
  if (['dish', 'dishes'].includes(key)) return 'dishes'
  if (['meal', 'meals'].includes(key)) return 'meals'
  return null
}

function profileSubTabFromKey(value) {
  const key = normalizeKey(value)
  if (!key) return null
  if (['photos', 'photo', 'gallery'].includes(key)) return 'photos'
  if (['info', 'details', 'profile'].includes(key)) return 'info'
  return null
}

function servicesSubTabFromKey(value) {
  const mealShares = normalizeMealShares(value)
  if (mealShares) return mealShares
  const key = normalizeKey(value)
  if (!key) return null
  if (['services', 'service', 'offerings', 'offering'].includes(key)) return 'services'
  return null
}

function buildLabel(result) {
  if (result.menuSubTab) return MENU_SUBTAB_LABELS[result.menuSubTab] || formatLabel(result.menuSubTab)
  if (result.servicesSubTab) return SERVICES_SUBTAB_LABELS[result.servicesSubTab] || formatLabel(result.servicesSubTab)
  if (result.profileSubTab) return PROFILE_SUBTAB_LABELS[result.profileSubTab] || formatLabel(result.profileSubTab)
  if (result.tab) return MAIN_TAB_LABELS[result.tab] || formatLabel(result.tab)
  return null
}

export function resolveSousChefNavigation(payload = {}) {
  const rawTab = payload?.tab ?? payload?.target_tab ?? payload?.targetTab ?? payload?.target
  const rawSubTab = payload?.sub_tab ?? payload?.subTab ?? payload?.menu_sub_tab ?? payload?.services_sub_tab ?? payload?.profile_sub_tab
  const normalizedTab = normalizeKey(rawTab)
  const normalizedSubTab = normalizeKey(rawSubTab)

  const result = {
    tab: null,
    menuSubTab: null,
    servicesSubTab: null,
    profileSubTab: null,
    label: null
  }

  if (!normalizedTab && !normalizedSubTab) return result

  const mealShares = normalizeMealShares(normalizedTab)
  if (mealShares) {
    result.tab = 'services'
    result.servicesSubTab = 'meal-shares'
    result.label = buildLabel(result)
    return result
  }

  const menuSubTab = menuSubTabFromKey(normalizedTab)
  if (menuSubTab) {
    result.tab = 'menu'
    result.menuSubTab = menuSubTab
    result.label = buildLabel(result)
    return result
  }

  const profileSubTab = profileSubTabFromKey(normalizedTab)
  if (profileSubTab && normalizedTab !== 'profile') {
    result.tab = 'profile'
    result.profileSubTab = profileSubTab
    result.label = buildLabel(result)
    return result
  }

  const tabAlias = TAB_ALIASES[normalizedTab] || normalizedTab
  if (tabAlias) {
    result.tab = tabAlias
  }

  if (tabAlias === 'services') {
    const subTab = servicesSubTabFromKey(normalizedSubTab)
    if (subTab) result.servicesSubTab = subTab
  }

  if (tabAlias === 'menu') {
    const subTab = menuSubTabFromKey(normalizedSubTab)
    if (subTab) result.menuSubTab = subTab
  }

  if (tabAlias === 'profile') {
    const subTab = profileSubTabFromKey(normalizedSubTab)
    if (subTab) result.profileSubTab = subTab
  }

  result.label = buildLabel(result)

  return result
}

export function resolveSousChefPrefillTarget(payload = {}) {
  if (payload?.target_tab || payload?.targetTab || payload?.sub_tab || payload?.subTab) {
    return resolveSousChefNavigation({
      tab: payload?.target_tab ?? payload?.targetTab,
      sub_tab: payload?.sub_tab ?? payload?.subTab
    })
  }

  const formType = normalizeKey(payload?.form_type ?? payload?.formType)
  const result = {
    tab: null,
    menuSubTab: null,
    servicesSubTab: null,
    profileSubTab: null,
    label: null
  }

  switch (formType) {
    case 'ingredient':
      result.tab = 'menu'
      result.menuSubTab = 'ingredients'
      break
    case 'dish':
      result.tab = 'menu'
      result.menuSubTab = 'dishes'
      break
    case 'meal':
      result.tab = 'menu'
      result.menuSubTab = 'meals'
      break
    case 'event':
      result.tab = 'services'
      result.servicesSubTab = 'meal-shares'
      break
    case 'service':
      result.tab = 'services'
      result.servicesSubTab = 'services'
      break
    default:
      return result
  }

  result.label = buildLabel(result)

  return result
}

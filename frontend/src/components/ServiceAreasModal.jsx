import React, { useMemo, useState } from 'react'
import { countryNameFromCode } from '../utils/geo.js'

/**
 * ServiceAreasModal - Slide-in panel showing all service areas for a chef
 * 
 * Features:
 * - Slide-in animation from right
 * - Groups areas by country/region
 * - Shows user's area status for authenticated users
 * - Search/filter functionality
 * - Light/dark theme support
 */

/**
 * Process raw serving_postalcodes into structured area data
 * Returns grouped areas by country with cities
 */
function processAreas(areas) {
  if (!Array.isArray(areas) || areas.length === 0) return { countries: [], totalCount: 0 }

  const byCountry = new Map()

  for (const p of areas) {
    const countryCode = p?.country?.code || p?.country || ''
    const countryName = p?.country?.name || (countryCode.length === 2 ? countryNameFromCode(countryCode) : countryCode) || 'Unknown'
    const city = (p?.city || p?.place_name || '').trim()
    const postalCode = p?.postal_code || p?.postalcode || p?.code || ''

    const key = countryCode || countryName

    if (!byCountry.has(key)) {
      byCountry.set(key, {
        code: countryCode,
        name: countryName,
        cities: new Map(),
        postalCodes: new Set(),
        count: 0
      })
    }

    const country = byCountry.get(key)
    country.count++
    if (postalCode) country.postalCodes.add(postalCode)

    if (city) {
      if (!country.cities.has(city)) {
        country.cities.set(city, { name: city, postalCodes: new Set() })
      }
      if (postalCode) country.cities.get(city).postalCodes.add(postalCode)
    }
  }

  // Convert to array and sort
  const countries = Array.from(byCountry.values()).map(c => ({
    ...c,
    cities: Array.from(c.cities.values())
      .sort((a, b) => a.name.localeCompare(b.name)),
    postalCodes: Array.from(c.postalCodes)
  })).sort((a, b) => b.count - a.count)

  return {
    countries,
    totalCount: areas.length
  }
}

/**
 * Get the primary display city for a chef's service areas
 */
export function getPrimaryCity(areas) {
  if (!Array.isArray(areas) || areas.length === 0) return null

  // Find the first city name available
  for (const p of areas) {
    const city = (p?.city || p?.place_name || '').trim()
    if (city) return city
  }
  return null
}

/**
 * Get a summary of areas for display on cards
 * Returns: { primaryCity, countryCode, countryName, totalAreas, additionalCities, uniqueCities }
 */
export function getAreaSummary(areas) {
  if (!Array.isArray(areas) || areas.length === 0) {
    return { primaryCity: null, countryCode: null, countryName: null, totalAreas: 0, additionalCities: [], uniqueCities: 0 }
  }

  const { countries, totalCount } = processAreas(areas)
  
  if (countries.length === 0) {
    return { primaryCity: null, countryCode: null, countryName: null, totalAreas: 0, additionalCities: [], uniqueCities: 0 }
  }

  const primaryCountry = countries[0]
  const allCities = primaryCountry.cities.map(c => c.name)
  const primaryCity = allCities[0] || null
  const additionalCities = allCities.slice(1, 4)
  const uniqueCities = allCities.length

  return {
    primaryCity,
    countryCode: primaryCountry.code,
    countryName: primaryCountry.name,
    totalAreas: totalCount,
    additionalCities,
    uniqueCities,
    otherCountries: countries.slice(1)
  }
}

/**
 * Country flag emoji from code
 */
function countryFlag(code) {
  if (!code || code.length !== 2) return '🌍'
  const codePoints = [...code.toUpperCase()].map(char => 127397 + char.charCodeAt(0))
  return String.fromCodePoint(...codePoints)
}

export default function ServiceAreasModal({
  open,
  onClose,
  areas = [],
  chefName = 'Chef',
  userPostalCode = null,
  userCountry = null,
  servesUser = null // true/false/null (null = unknown)
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedCities, setExpandedCities] = useState(new Set())

  // Toggle city expansion
  const toggleCity = (cityKey) => {
    setExpandedCities(prev => {
      const next = new Set(prev)
      if (next.has(cityKey)) {
        next.delete(cityKey)
      } else {
        next.add(cityKey)
      }
      return next
    })
  }

  const { countries, totalCount } = useMemo(() => processAreas(areas), [areas])

  // Normalize postal code for comparison (remove delimiters like hyphens, spaces)
  const normalizePostalCode = (code) => code.toUpperCase().replace(/[^A-Z0-9]/g, '')

  // Check if a postal code matches the search query
  const postalCodeMatches = (pc, query, normalizedQuery) => {
    const pcLower = pc.toLowerCase()
    const pcNormalized = normalizePostalCode(pc)
    // Match against original format OR normalized format
    return pcLower.includes(query) || pcNormalized.includes(normalizedQuery)
  }

  // Filter areas based on search query
  const filteredCountries = useMemo(() => {
    if (!searchQuery.trim()) return countries

    const q = searchQuery.toLowerCase().trim()
    const qNormalized = normalizePostalCode(searchQuery)
    
    return countries
      .map(country => {
        // Check if country name matches
        if (country.name.toLowerCase().includes(q)) return country

        // Filter cities that match
        const matchingCities = country.cities.filter(city =>
          city.name.toLowerCase().includes(q) ||
          Array.from(city.postalCodes).some(pc => postalCodeMatches(pc, q, qNormalized))
        )

        // Also check postal codes at country level
        const matchingPostals = country.postalCodes.filter(pc => postalCodeMatches(pc, q, qNormalized))

        if (matchingCities.length > 0 || matchingPostals.length > 0) {
          return {
            ...country,
            cities: matchingCities.length > 0 ? matchingCities : country.cities
          }
        }
        return null
      })
      .filter(Boolean)
  }, [countries, searchQuery])

  // Check if user's area is in the list
  const userAreaMatch = useMemo(() => {
    if (!userPostalCode) return null

    const normalizedUserPC = userPostalCode.toUpperCase().replace(/[^A-Z0-9]/g, '')

    for (const country of countries) {
      if (userCountry && country.code && country.code !== userCountry) continue

      for (const pc of country.postalCodes) {
        const normalizedPC = pc.toUpperCase().replace(/[^A-Z0-9]/g, '')
        if (normalizedPC === normalizedUserPC) {
          return {
            country: country.name,
            postalCode: pc
          }
        }
      }
    }
    return null
  }, [countries, userPostalCode, userCountry])

  if (!open) return null

  return (
    <>
      {/* Overlay */}
      <div
        className="service-areas-modal-overlay"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-in Panel */}
      <aside
        className="service-areas-modal"
        role="dialog"
        aria-label={`Service areas for ${chefName}`}
        aria-modal="true"
      >
        {/* Header */}
        <div className="service-areas-modal-header">
          <div className="service-areas-modal-title">
            <i className="fa-solid fa-map-location-dot"></i>
            <div>
              <h2>Service Areas</h2>
              <p className="muted">{chefName} serves {totalCount} {totalCount === 1 ? 'area' : 'areas'}</p>
            </div>
          </div>
          <button
            className="service-areas-modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        {/* User Status Banner */}
        {servesUser !== null && (
          <div className={`service-areas-user-status ${servesUser ? 'serves' : 'no-serve'}`}>
            <div className="status-icon">
              <i className={`fa-solid fa-${servesUser ? 'circle-check' : 'circle-xmark'}`}></i>
            </div>
            <div className="status-text">
              {servesUser ? (
                <>
                  <strong>Available in your area</strong>
                  <span className="muted">
                    {userAreaMatch
                      ? `Serves ${userAreaMatch.postalCode} in ${userAreaMatch.country}`
                      : userPostalCode
                        ? `Your location: ${userPostalCode}`
                        : 'This chef can serve your location'}
                  </span>
                </>
              ) : (
                <>
                  <strong>Outside service area</strong>
                  <span className="muted">
                    {userPostalCode
                      ? `${userPostalCode} is not currently served`
                      : 'Your location is not in this chef\'s service area'}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Search */}
        <div className="service-areas-search">
          <div className="search-input-wrapper">
            <i className="fa-solid fa-search"></i>
            <input
              type="text"
              placeholder="Search cities or postal codes..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button
                className="search-clear"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search"
              >
                <i className="fa-solid fa-times"></i>
              </button>
            )}
          </div>
        </div>

        {/* Areas List */}
        <div className="service-areas-content">
          {filteredCountries.length === 0 ? (
            <div className="service-areas-empty">
              <i className="fa-solid fa-map-marker-alt"></i>
              <p>No areas match "{searchQuery}"</p>
              <button className="btn btn-outline btn-sm" onClick={() => setSearchQuery('')}>
                Clear search
              </button>
            </div>
          ) : (
            filteredCountries.map((country, idx) => (
              <div key={country.code || idx} className="service-area-country">
                <div className="country-header">
                  <span className="country-flag">{countryFlag(country.code)}</span>
                  <span className="country-name">{country.name}</span>
                  <span className="country-count">{country.count} {country.count === 1 ? 'area' : 'areas'}</span>
                </div>

                {country.cities.length > 0 ? (
                  <div className="city-list">
                    {country.cities.map((city, cityIdx) => {
                      const cityKey = `${country.code}-${city.name}`
                      const isExpanded = expandedCities.has(cityKey)
                      const isUserCity = userAreaMatch &&
                        Array.from(city.postalCodes).some(pc =>
                          pc.toUpperCase().replace(/[^A-Z0-9]/g, '') ===
                          (userPostalCode || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
                        )
                      const postalCodesArray = Array.from(city.postalCodes)

                      return (
                        <div
                          key={cityIdx}
                          className={`city-card-expandable ${isUserCity ? 'user-area' : ''} ${isExpanded ? 'expanded' : ''}`}
                        >
                          <button
                            className="city-card-header"
                            onClick={() => toggleCity(cityKey)}
                            aria-expanded={isExpanded}
                          >
                            <div className="city-name">
                              <i className="fa-solid fa-location-dot"></i>
                              <span>{city.name}</span>
                              {isUserCity && (
                                <span className="your-area-badge">Your area</span>
                              )}
                            </div>
                            <div className="city-meta">
                              {city.postalCodes.size > 0 && (
                                <span className="city-postcodes-count">
                                  {city.postalCodes.size} {city.postalCodes.size === 1 ? 'code' : 'codes'}
                                </span>
                              )}
                              <i className={`fa-solid fa-chevron-${isExpanded ? 'up' : 'down'} expand-icon`}></i>
                            </div>
                          </button>
                          {isExpanded && postalCodesArray.length > 0 && (
                            <div className="city-postal-codes">
                              {postalCodesArray.map((pc, pcIdx) => {
                                const isUserPostal = userPostalCode &&
                                  pc.toUpperCase().replace(/[^A-Z0-9]/g, '') ===
                                  userPostalCode.toUpperCase().replace(/[^A-Z0-9]/g, '')

                                return (
                                  <span
                                    key={pcIdx}
                                    className={`postal-code-tag ${isUserPostal ? 'user-area' : ''}`}
                                  >
                                    {pc}
                                    {isUserPostal && <i className="fa-solid fa-check"></i>}
                                  </span>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  /* When no city names are available, show the postal codes directly */
                  <div className="postal-codes-grid">
                    {country.postalCodes.slice(0, 50).map((pc, pcIdx) => {
                      const isUserPostal = userPostalCode &&
                        pc.toUpperCase().replace(/[^A-Z0-9]/g, '') ===
                        userPostalCode.toUpperCase().replace(/[^A-Z0-9]/g, '')

                      return (
                        <div
                          key={pcIdx}
                          className={`postal-code-chip ${isUserPostal ? 'user-area' : ''}`}
                        >
                          <span>{pc}</span>
                          {isUserPostal && (
                            <i className="fa-solid fa-check" title="Your area"></i>
                          )}
                        </div>
                      )
                    })}
                    {country.postalCodes.length > 50 && (
                      <div className="postal-code-chip more">
                        +{country.postalCodes.length - 50} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="service-areas-footer">
          <button className="btn btn-outline" onClick={onClose}>
            Close
          </button>
        </div>
      </aside>
    </>
  )
}

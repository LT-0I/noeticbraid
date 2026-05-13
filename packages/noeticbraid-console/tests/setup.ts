import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import i18n, { localeStorageKey } from '../src/i18n'
import { server } from '../src/mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(async () => {
  window.localStorage.setItem(localeStorageKey, 'en-US')
  await i18n.changeLanguage('en-US')
})
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

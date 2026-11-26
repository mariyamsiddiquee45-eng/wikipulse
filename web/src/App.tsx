import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LoadingBlock } from './components/States'

const HomePage = lazy(() =>
  import('./pages/HomePage').then((module) => ({ default: module.HomePage })),
)
const DayPage = lazy(() =>
  import('./pages/DayPage').then((module) => ({ default: module.DayPage })),
)
const EventPage = lazy(() =>
  import('./pages/EventPage').then((module) => ({ default: module.EventPage })),
)
const ArticlePage = lazy(() =>
  import('./pages/ArticlePage').then((module) => ({ default: module.ArticlePage })),
)
const SearchPage = lazy(() =>
  import('./pages/SearchPage').then((module) => ({ default: module.SearchPage })),
)
const MethodsPage = lazy(() =>
  import('./pages/MethodsPage').then((module) => ({ default: module.MethodsPage })),
)
const AboutPage = lazy(() =>
  import('./pages/AboutPage').then((module) => ({ default: module.AboutPage })),
)
const PrivacyPage = lazy(() =>
  import('./pages/PrivacyPage').then((module) => ({ default: module.PrivacyPage })),
)
const NotFoundPage = lazy(() =>
  import('./pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })),
)

function ScrollToTop() {
  const location = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [location.pathname])
  return null
}

function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Suspense
        fallback={
          <div className="container page-main">
            <LoadingBlock lines={6} />
          </div>
        }
      >
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="d/:date" element={<DayPage />} />
            <Route path="e/:id" element={<EventPage />} />
            <Route path="a/:slug" element={<ArticlePage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="methods" element={<MethodsPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="privacy" element={<PrivacyPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App

import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Home from './pages/Home.jsx'
import StudyGuide from './pages/StudyGuide.jsx'
import RolePlan from './pages/RolePlan.jsx'
import Jobs from './pages/Jobs.jsx'
import Skills from './pages/Skills.jsx'
import SkillDetail from './pages/SkillDetail.jsx'
import Market from './pages/Market.jsx'
import Candidates from './pages/Candidates.jsx'
import CandidateDetail from './pages/CandidateDetail.jsx'

// Two audiences, labelled. A person can be both, so these are groups in one bar
// rather than a mode switch that makes you feel you have left the site.
const SEEKER = [
  ['/study', 'What jobs need'],
  ['/jobs', 'Jobs'],
  ['/skills', 'Skills'],
]
const RECRUITER = [
  ['/market', 'Market'],
  ['/candidates', 'Candidates'],
]

function ScrollTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <header className="rail">
        <div className="wrap">
          <NavLink className="brand" to="/">
            <span>Career<em>Link</em>
              <small>Find work. Find candidates.</small>
            </span>
          </NavLink>
          <nav>
            <NavLink to="/" end className={({ isActive }) => (isActive ? 'on' : '')}>Home</NavLink>
            <span className="navgroup">Job seekers</span>
            {SEEKER.map(([to, label]) => (
              <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'on' : '')}>{label}</NavLink>
            ))}
            <span className="navgroup">Recruiters</span>
            {RECRUITER.map(([to, label]) => (
              <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'on' : '')}>{label}</NavLink>
            ))}
          </nav>
        </div>
      </header>

      <ScrollTop />
      <main className="wrap">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/study" element={<StudyGuide />} />
          <Route path="/study/:role" element={<RolePlan />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/skills/:skill" element={<SkillDetail />} />
          <Route path="/market" element={<Market />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/candidates/:id" element={<CandidateDetail />} />
          <Route path="*" element={
            <div className="empty"><b>That page does not exist.</b><br />
              Try the Study guide or Jobs from the menu above.</div>} />
        </Routes>
      </main>

      <footer>
        <div className="wrap">
          <p>CareerLink is built on 58,954 real job adverts and a skills index
            covering 176 tools. A dash means the advert did not say, not that the
            answer is zero.</p>
          <p><a href="/analysis">How this data was checked</a><br />
            Method, gaps, and what they stop the site from claiming.</p>
        </div>
      </footer>
    </>
  )
}

import { useState } from 'react'
import './App.css'
import Start from './components/Start'
import Onboard from './components/Onboard'

// Displays main page
const App = () => {
  
  // Checking to see if the user pressed the start button
  const [started, setStarted] = useState(false)

  if (!started) {
    return <Start onStart={() => setStarted(true)}/>
  }

  return <Onboard/>
}

export default App

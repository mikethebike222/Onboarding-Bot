import { useEffect, useState, useRef } from "react"
import styles from './Onboard.module.css'

// Create socket to connect with the chat server to simplify frontend logic
// Replace 127.0.0.1:8000/ with whatever it says from django
const socket = new WebSocket("ws://127.0.0.1:8000/ws/chat/")

/**
 * This is the page that gets loaded into when the user clicks the Start Button.
 * It displays the chatbot conversation concurrently until all information is recieved from the user.
 */
const Onboard = () => {

  // Stores all the Messages between the User and the chatBot
  // Initalized with a welcome message
    const [allMessages, setAllMsg] = useState<{text: string, isUser: boolean}[]>([
        {text: "Hi! I'm going to be helping you get onboarded today. Let's start off with your ZipCode", isUser: false}
    ])

    // Tracks the User Input 
    const [input, setInput] = useState("")

    // Checker to see if we are done yet
    const [isComplete, setIsComplete] = useState(false) 

    // References invisible div at the bottom of the messages container and is used for scrolling
    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Autoscrolling to ensure latest message is always displayed
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [allMessages])

    // Listens to the Web Socket for response from the server
    useEffect(() => {
        socket.onmessage = (event) => {
            const data = JSON.parse(event.data)
            
            // Check if the message indicates completion which is hardcoded to be Information collected:
            if (data.message.includes("Information collected:")) {
                setIsComplete(true)
            }
            
            setAllMsg(prev => [...prev, {text: data.message, isUser: false}])
        }
    }, [])
    

    // Sends Users Message to the Server
    const sendMessage = () => {
        // Just in case dont let them send if complete or if nothing is there
        if (!input.trim() || isComplete) return 

        setAllMsg(prev => [...prev, {text: input, isUser: true}])
        socket.send(JSON.stringify({ message: input }))
        setInput("")
    }
      
    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <h2>Let's Get You Onboarded!</h2>
                {isComplete && (
                    <div className={styles.completeStatus}>
                        Onboarding Complete!
                    </div>
                )}
            </div>
            
            <div className={styles.messagesContainer}>
                {allMessages.map((msg, i) => (
                    <div key={i} className={msg.isUser ? styles.message + ' ' + styles.userMessage : styles.message + ' ' + styles.botMessage}>
                        {msg.text}
                    </div>
                ))}
                <div ref={messagesEndRef}/>
            </div>
            
            <div className={styles.inputContainer}>
                {!isComplete ? (
                    <>
                        <input className={styles.input} value={input} onChange={(e) => setInput(e.target.value)} 
                        onKeyDown={(e) => e.key === 'Enter' && sendMessage()}placeholder="Type your message..."/>
                        <button className={styles.sendButton}onClick={sendMessage}disabled={!input.trim()}>
                            Send
                        </button>
                    </>
                ) : (
                    <div className={styles.completionMessage}>
                        Thank you for completing the onboarding process!
                    </div>
                )}
            </div>
        </div>
    )
}

export default Onboard
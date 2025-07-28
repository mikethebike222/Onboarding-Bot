import styles from './Start.module.css'

// This is the page that gets loaded initially and loads a button to start the chat
const Start = ({onStart}:{onStart: () => void}) => {
    return (
        <div className={styles.container}> 
            <h1> Welcome to our Onboarding Process!</h1>
            <button onClick={onStart}> Click Here to Start the Process</button>
        </div>
    )
}


export default Start
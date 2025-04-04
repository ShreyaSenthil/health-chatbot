import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
    const [message, setMessage] = useState("");
    const [chatHistory, setChatHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [file, setFile] = useState(null);
    const chatBoxRef = useRef(null);

    const userId = "user123";  // 🔹 Set a unique user ID

    useEffect(() => {
        fetchChatHistory();
    }, []);

    useEffect(() => {
        chatBoxRef.current?.scrollTo({
            top: chatBoxRef.current.scrollHeight,
            behavior: "smooth",
        });
    }, [chatHistory]);

    // 🔹 Fetch past chat messages from the database
    const fetchChatHistory = async () => {
        try {
            const res = await axios.get(`http://localhost:8000/chat/history?user_id=${userId}`);
            const formattedHistory = res.data.history.map(chat => ({
                sender: chat.sender === "user" ? "You" : "Bot",
                text: chat.text,
                timestamp: new Date(chat.timestamp).toLocaleTimeString(),
            }));
            setChatHistory(formattedHistory);
        } catch (error) {
            console.error("Error fetching chat history:", error);
        }
    };

    const handleFileChange = (event) => {
        setFile(event.target.files[0]);
    };

    const sendMessage = async () => {
        if (!message.trim()) return;
        setLoading(true);

        const userMessage = { sender: "You", text: message, timestamp: new Date().toLocaleTimeString() };
        setChatHistory((prev) => [...prev, userMessage]);

        try {
            const formData = new FormData();
            formData.append("user_id", userId);
            formData.append("message", message);

            if (file) {
                formData.append("file", file);
            }

            const res = await axios.post("http://localhost:8000/chat/", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });

            const botMessage = { sender: "Bot", text: res.data.response, timestamp: new Date().toLocaleTimeString() };
            setChatHistory((prev) => [...prev, botMessage]);
        } catch (error) {
            setChatHistory((prev) => [...prev, { sender: "Bot", text: "❌ Error connecting to server.", timestamp: new Date().toLocaleTimeString() }]);
        }

        setMessage("");
        setLoading(false);
    };

    return (
        <div className="chat-container">
            <h1>🩺 WellBot</h1>
            <div className="chat-box" ref={chatBoxRef}>
                {chatHistory.map((msg, index) => (
                    <div key={index} className={`message ${msg.sender === "You" ? "user-msg" : "bot-msg"}`}>
                        <p dangerouslySetInnerHTML={{ __html: msg.text.replace(/\n/g, "<br>") }}></p>
                        <span className="timestamp">{msg.timestamp}</span>
                    </div>
                ))}
                {loading && <p className="typing-indicator">Bot is typing...</p>}
            </div>

            <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask me about health, diet, and wellness..."
                rows="3"
            />
            <br />
            <input type="file" onChange={handleFileChange} />
            <br />
            <button onClick={sendMessage} disabled={loading}>{loading ? "⏳ Thinking..." : "Send"}</button>
        </div>
    );
}

export default App;

import { useState } from 'react'

function App() {
    const [count, setCount] = useState(0)

    return (
        <div className="flex h-screen items-center justify-center bg-background text-foreground">
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold tracking-tight">Momentum</h1>
                <p className="text-lg text-muted-foreground">A-Share Visual Stock Selection & Quantitative Trading System</p>
                <div className="mt-8">
                    <button
                        className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 transition"
                        onClick={() => setCount((count) => count + 1)}
                    >
                        Count is {count}
                    </button>
                </div>
            </div>
        </div>
    )
}

export default App

import { ChatWindow } from "./components/ChatWindow";

const SDG_BADGES = [
  { number: "11", label: "Sustainable Cities",         color: "bg-orange-500" },
  { number: "6",  label: "Clean Water",                color: "bg-blue-500" },
  { number: "12", label: "Responsible Consumption",    color: "bg-yellow-600" },
  { number: "13", label: "Climate Action",             color: "bg-green-700" },
];

export default function App() {
  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* App header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-green-500 flex items-center justify-center">
            <span className="text-white text-sm font-bold select-none">CA</span>
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-900 leading-tight">CivicAI</h1>
            <p className="text-xs text-gray-500 leading-tight">
              AI Sustainability Assistant
            </p>
          </div>
        </div>

        {/* SDG alignment badges */}
        <div className="hidden sm:flex items-center gap-1.5">
          {SDG_BADGES.map((sdg) => (
            <span
              key={sdg.number}
              title={`SDG ${sdg.number}: ${sdg.label}`}
              className={`${sdg.color} text-white text-xs font-bold px-2 py-0.5 rounded select-none`}
            >
              SDG {sdg.number}
            </span>
          ))}
        </div>
      </header>

      {/* Chat area — fills remaining height */}
      <main className="flex-1 overflow-hidden max-w-3xl w-full mx-auto flex flex-col">
        <ChatWindow />
      </main>
    </div>
  );
}

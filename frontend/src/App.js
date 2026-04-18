import { useState, useRef, useEffect } from "react";
import "./App.css";

const AGENT_URL = "http://127.0.0.1:8000/chat";
const DATES_URL = "http://127.0.0.1:8000/dates";

const MONTHS_TR = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                   "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
const DAYS_TR   = ["Pt","Sa","Ça","Pe","Cu","Ct","Pz"];

const CITY_TO_CODE = {
  istanbul: "IST", ist: "IST",
  izmir: "ADB", adb: "ADB",
  ankara: "ESB", esb: "ESB",
  frankfurt: "FRA", fra: "FRA",
  antalya: "AYT", ayt: "AYT",
};

function detectRoute(messages) {
  const userMsgs = messages.filter(m => m.role === "user").slice(-3);
  const text = userMsgs
    .map(m => m.content || "")
    .join(" ")
    .toLowerCase()
    .replace(/(istanbul|izmir|ankara|frankfurt|antalya)[a-zışğüöç]*/g, m => {
      for (const k of Object.keys(CITY_TO_CODE)) if (m.startsWith(k)) return k;
      return m;
    });
  const words = text.split(/\s+/);
  const found = [...new Set(words.map(w => CITY_TO_CODE[w]).filter(Boolean))];
  if (found.length >= 2) return { from: found[0], to: found[1] };
  return null;
}

function InlineDatePicker({ route, onSelect }) {
  const [dates, setDates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!route) { setLoading(false); return; }
    fetch(`${DATES_URL}?from=${route.from}&to=${route.to}`)
      .then(r => r.json())
      .then(d => { setDates(d.dates || []); setLoading(false); })
      .catch(() => { setDates([]); setLoading(false); });
  }, [route]);

  if (loading) return (
    <div style={ids.wrap}>
      <div style={ids.header}>
        {route ? `✈ ${route.from} → ${route.to}` : "Uçuş Tarihleri"}
      </div>
      <div style={ids.loading}>Tarihler yükleniyor...</div>
    </div>
  );

  if (!dates.length) return (
    <div style={ids.wrap}>
      <div style={ids.header}>{route ? `✈ ${route.from} → ${route.to}` : "Uçuş Tarihleri"}</div>
      <div style={ids.empty}>Bu güzergahta mevcut uçuş bulunamadı.</div>
    </div>
  );

  const uniqueDays = Array.from(new Set(dates.map(iso => iso.split("T")[0])));
  const groups = {};
  uniqueDays.forEach(dayStr => {
    const d = new Date(dayStr + "T12:00:00");
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (!groups[key]) groups[key] = { year: d.getFullYear(), month: d.getMonth(), items: [] };
    groups[key].items.push(d);
  });

  return (
    <div style={ids.wrap}>
      <div style={ids.header}>
        {route ? `✈ ${route.from} → ${route.to} — Uygun Tarihler` : "Uygun Uçuş Tarihleri"}
      </div>
      <div style={ids.sub}>Seyahat etmek istediğiniz tarihi seçin</div>
      {Object.values(groups).map(g => (
        <div key={`${g.year}-${g.month}`} style={{ marginBottom: 12 }}>
          <div style={ids.monthLabel}>{MONTHS_TR[g.month]} {g.year}</div>
          <div style={ids.grid}>
            {g.items.map((d, i) => {
              const label = d.toLocaleDateString("tr-TR", {
                day: "numeric", month: "long", year: "numeric"
              });
              const dayIdx = (d.getDay() + 6) % 7;
              return (
                <button key={i} style={ids.card}
                  onMouseOver={e => Object.assign(e.currentTarget.style, ids.cardHover)}
                  onMouseOut={e => Object.assign(e.currentTarget.style, { background: "#fff", borderColor: "#ede8e1", transform: "none" })}
                  onClick={() => onSelect(label)}>
                  <span style={ids.dayName}>{DAYS_TR[dayIdx]}</span>
                  <span style={ids.dayNum}>{d.getDate()}</span>
                  <span style={ids.monthName}>{MONTHS_TR[g.month].slice(0,3)}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

const ids = {
  wrap: {
    background: "#fff", border: "1.5px solid #ede8e1",
    borderRadius: 16, padding: 16, marginTop: 8,
    boxShadow: "0 2px 8px rgba(0,0,0,.06)",
    maxWidth: 480, animation: "bbl-in .2s ease"
  },
  header: { fontSize: 13, fontWeight: 700, color: "#92400e", marginBottom: 4 },
  sub:    { fontSize: 11, color: "#a8a29e", marginBottom: 14 },
  loading:{ fontSize: 13, color: "#a8a29e", padding: "8px 0" },
  empty:  { fontSize: 13, color: "#a8a29e", padding: "8px 0" },
  monthLabel: {
    fontSize: 10, fontWeight: 700, color: "#a8a29e",
    textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 8
  },
  grid: { display: "flex", flexWrap: "wrap", gap: 8 },
  card: {
    display: "flex", flexDirection: "column", alignItems: "center",
    width: 60, padding: "10px 6px", borderRadius: 12,
    background: "#fff", border: "1.5px solid #ede8e1",
    cursor: "pointer", fontFamily: "inherit",
    transition: "all .15s", gap: 2
  },
  cardHover: { background: "#fffbeb", borderColor: "#f59e0b", transform: "translateY(-2px)" },
  dayName:  { fontSize: 10, color: "#a8a29e" },
  dayNum:   { fontSize: 20, fontWeight: 800, color: "#1c1917", lineHeight: 1.1 },
  monthName:{ fontSize: 10, fontWeight: 600, color: "#f59e0b" },
};

const ACTIONS = [
  { label: "Uçuş Sorgula", icon: "🔍", ic: "ic-q", desc: "Tarih, güzergah ve kişi sayısına göre uygun uçuşları listeleyin.", cta: "Aramaya başla →", msg: "Uçuş aramak istiyorum." },
  { label: "Bilet Satın Al", icon: "🎫", ic: "ic-b", desc: "Kendiniz veya aileniz için hızlıca bilet rezervasyonu yapın.", cta: "Bilet al →", msg: "Bilet satın almak istiyorum." },
  { label: "Check-in", icon: "✅", ic: "ic-c", desc: "Biletinizle check-in yaparak koltuk numaranızı alın.", cta: "Check-in yap →", msg: "Check-in yapmak istiyorum." },
];

function FlightCards({ data, onBook }) {
  const flights = data?.result?.available_flights || [];
  if (!flights.length) return null;
  return (
    <div className="flight-cards">
      {flights.map((f, i) => (
        <div key={i} className="flight-card">
          <div className="fc-header">
            <span className="fc-number">✈ {f["Flight number"]}</span>
            <span className="fc-duration">{f.duration} dk</span>
          </div>
          <div className="fc-route">
            <div className="fc-airport">
              <span className="fc-code">{data.args?.airport_from}</span>
              <span className="fc-time">{f.date_from}</span>
              <span className="fc-label">Kalkış</span>
            </div>
            <div className="fc-arrow">
              <div className="fc-line" />
              <span className="fc-plane">✈️</span>
              <div className="fc-line" />
            </div>
            <div className="fc-airport">
              <span className="fc-code">{data.args?.airport_to}</span>
              <span className="fc-time">{f.date_to}</span>
              <span className="fc-label">Varış</span>
            </div>
          </div>
          <button className="fc-book-btn"
            onClick={() => onBook(f["Flight number"])}>
            🎫 Bu Uçuşa Bilet Al
          </button>
        </div>
      ))}
    </div>
  );
}

function BookingCard({ data }) {
  const tickets = data?.result?.ticket_numbers || [];
  const names   = data?.args?.passenger_names || [];
  if (!tickets.length) return null;
  return (
    <div className="confirm-card">
      <div className="confirm-header">
        <div className="confirm-icon">✅</div>
        <div><div className="confirm-title">Bilet Onaylandı!</div><div className="confirm-sub">{tickets.length} bilet satın alındı</div></div>
      </div>
      <div className="confirm-flight">
        <span className="confirm-fn">✈ {data.args?.flight_number}</span>
        <span className="confirm-route">{tickets.length} yolcu</span>
      </div>
      <div className="confirm-tickets">
        {tickets.map((t, i) => (
          <div key={i} className="ticket-row">
            <span className="ticket-name">👤 {names[i] || `Yolcu ${i+1}`}</span>
            <span className="ticket-num">#{t}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckinCard({ data }) {
  const msg  = data?.result?.message || "";
  const seat = msg.match(/Koltuk numaranız: (\w+)/)?.[1] || "—";
  return (
    <div className="checkin-card">
      <div className="checkin-label">Koltuk Numaranız</div>
      <div className="checkin-seat">{seat}</div>
      <div className="checkin-name">✈ {data?.args?.flight_number} · {data?.args?.passenger_name}</div>
    </div>
  );
}

export default function App() {
  const [view, setView]           = useState("welcome");
  const [userName, setUserName]   = useState("");
  const [nameInput, setNameInput] = useState("");
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const bottomRef = useRef(null);
  const taRef     = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const resize = () => {
    const t = taRef.current; if (!t) return;
    t.style.height = "24px";
    t.style.height = Math.min(t.scrollHeight, 120) + "px";
  };

  const send = async (text) => {
    const txt = (text || input).trim();
    if (!txt || loading) return;

    const greeting = userName
      ? `Merhaba, ${userName}! ✈️ Size nasıl yardımcı olabilirim?`
      : "Merhaba! ✈️ Size nasıl yardımcı olabilirim?";

    const userMsg = { role: "user", content: txt };
    const init = messages.length === 0
      ? [{ role: "assistant", content: greeting, data: null, action: null }, userMsg]
      : [...messages, userMsg];

    setMessages(init);
    setInput("");
    if (taRef.current) taRef.current.style.height = "24px";
    setView("chat");
    setLoading(true);

    try {
      const res  = await fetch(AGENT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: init.map(m => ({ role: m.role, content: m.content })) })
      });
      const json = await res.json();
      const route = json.route || detectRoute(init);
      setMessages([...init, {
        role: "assistant",
        content: json.reply,
        data: json.data,
        action: json.action,
        route: route
      }]);
    } catch {
      setMessages([...init, { role: "assistant", content: "Bağlantı hatası. Lütfen tekrar deneyin.", data: null, action: null }]);
    } finally {
      setLoading(false);
    }
  };

  const handleDateSelect = (dateLabel) => {
    send(dateLabel);
  };

  const confirmName = () => { if (nameInput.trim()) setUserName(nameInput.trim()); };
  const onKey  = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  const onWKey = (e) => { if (e.key === "Enter") { e.preventDefault(); send(input); } };
  const onNKey = (e) => { if (e.key === "Enter") confirmName(); };

  if (view === "welcome") return (
    <>
      <div className="welcome">
        <div className="w-orb" />
        <div className="w-name-box">
          <span style={{ fontSize: 16 }}>👤</span>
          <input placeholder="Adınız nedir? (opsiyonel)" value={nameInput}
            onChange={e => setNameInput(e.target.value)} onKeyDown={onNKey} onBlur={confirmName} />
          {nameInput && <span className="w-name-hint">Enter ↵</span>}
        </div>
        <div className="w-greeting">{userName ? `Hoş geldiniz, ${userName} 👋` : "Hoş geldiniz"}</div>
        <div className="w-title">Size nasıl<br /><span>yardımcı olabilirim?</span></div>
        <div className="w-cards">
          {ACTIONS.map(a => (
            <button key={a.label} className="w-card" onClick={() => send(a.msg)}>
              <div className={`w-card-icon ${a.ic}`}>{a.icon}</div>
              <div className="w-card-title">{a.label}</div>
              <div className="w-card-desc">{a.desc}</div>
              <div className="w-card-cta">{a.cta}</div>
            </button>
          ))}
        </div>
        <div className="w-input-wrap">
          <div className="w-input-box">
            <span style={{ fontSize: 16, flexShrink: 0 }}>✈️</span>
            <input placeholder="Bir şey yazın veya yukarıdan seçin..." value={input}
              onChange={e => setInput(e.target.value)} onKeyDown={onWKey} />
            <button className="w-send" onClick={() => send(input)} disabled={!input.trim()}>➤</button>
          </div>
          <div className="w-hint">Enter ile gönderin</div>
        </div>
      </div>
    </>
  );

  return (
    <>
      <div className="chat-view">
        <div className="chat-top">
          <button className="back-btn" onClick={() => { setView("welcome"); setMessages([]); }}>←</button>
          <div className="ct-logo">✈️</div>
          <div className="ct-info">
            <div className="ct-title">{userName ? `Merhaba, ${userName}` : "SLA Flight Assistant"}</div>
            <div className="ct-sub">Groq · Llama 3.3</div>
          </div>
          <div className="ct-badge">● Bağlı</div>
        </div>

        <div className="quick-pills">
          {ACTIONS.map(a => (
            <button key={a.label} className="pill" onClick={() => send(a.msg)}>{a.icon} {a.label}</button>
          ))}
        </div>

        <div className="msgs">
          {messages.map((m, i) => (
            <div key={i} className={`grp ${m.role}`}>
              <div className="grp-lbl">{m.role === "user" ? (userName || "Siz") : "Agent"}</div>
              {m.content && <div className={`bbl ${m.role}`}>{m.content}</div>}

              {(() => {
                const isLastAssistant = i === messages.length - 1 && m.role === "assistant";
                if (!isLastAssistant) return null;
                if (!m.route || !m.route.from || !m.route.to) return null;
                const hasDate = messages.some(msg =>
                  msg.role === "user" && (
                    /\d{1,2}\s+(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)/i.test(msg.content || "") ||
                    /\d{4}-\d{2}-\d{2}/.test(msg.content || "")
                  )
                );
                if (hasDate) return null;
                return <InlineDatePicker route={m.route} onSelect={handleDateSelect} />;
              })()}

              {m.data?.type === "query_flight" && (() => {
                
                // Hide if any later user message mentions a flight number
                const userPickedLater = messages.slice(i+1).some(later =>
                  later.role === "user" && /TK\d+/i.test(later.content || "")
                );
                // Hide if any later assistant message has a successful booking
                const bookedLater = messages.slice(i+1).some(later =>
                  later.role === "assistant" &&
                  later.data?.type === "book_flight" &&
                  later.data?.result?.transaction_status === "Success"
                );
                // Hide if this is not the last assistant message (user already moved on)
                const isStale = messages.slice(i+1).some(later => later.role === "assistant");
                if (userPickedLater || bookedLater || isStale) return null;
                return <FlightCards data={m.data} onBook={(fn) => send(`${fn} uçuşuna bilet almak istiyorum.`)} />;
              })()}
              {m.data?.type === "book_flight" && m.data?.result?.transaction_status === "Success" && (
                <BookingCard data={m.data} />
              )}
              {m.data?.type === "check_in" && m.data?.result?.transaction_status === "Success" && (
                <CheckinCard data={m.data} />
              )}
            </div>
          ))}

          {loading && (
            <div className="grp assistant">
              <div className="grp-lbl">Agent</div>
              <div className="typing-bbl"><span /><span /><span /></div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="input-wrap">
          <div className="input-inner">
            <textarea ref={taRef} placeholder="Mesajınızı yazın..."
              value={input} onChange={e => { setInput(e.target.value); resize(); }}
              onKeyDown={onKey} rows={1} />
            <button className="send-btn" onClick={() => send()} disabled={loading || !input.trim()}>➤</button>
          </div>
          <div className="input-hint">Enter ile gönderin · Shift+Enter yeni satır</div>
        </div>
      </div>
    </>
  );
}

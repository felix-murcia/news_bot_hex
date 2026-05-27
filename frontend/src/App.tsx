import { useState } from "react";
import { Layout } from "./components/Layout";
import { Tabs } from "./components/Tabs";
import { NewsTab } from "./features/news/NewsTab";
import { AudioTab } from "./features/audio/AudioTab";
import { VideoTab } from "./features/video/VideoTab";
import { TimerSettings } from "./components/TimerSettings";

const TABS = [
  { id: "news", label: "News" },
  { id: "audio", label: "Audio" },
  { id: "video", label: "Video" },
  { id: "settings", label: "⚙️ Configuración" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("news");

  return (
    <Layout>
      <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
      <div className={activeTab === "news" ? undefined : "hidden"}><NewsTab /></div>
      <div className={activeTab === "audio" ? undefined : "hidden"}><AudioTab /></div>
      <div className={activeTab === "video" ? undefined : "hidden"}><VideoTab /></div>
      <div className={activeTab === "settings" ? undefined : "hidden"}><TimerSettings /></div>
    </Layout>
  );
}

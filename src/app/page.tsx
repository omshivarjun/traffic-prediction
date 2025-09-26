import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
        <div className="flex items-center gap-4 mb-8">
          <div className="text-6xl">🚦</div>
          <div>
            <h1 className="text-3xl font-bold text-gray-800">Real-Time Traffic Congestion Prediction</h1>
            <p className="text-lg text-gray-600 mt-2">Kafka + Hadoop Streaming Pipeline</p>
          </div>
        </div>
        
        <div className="max-w-4xl text-center sm:text-left">
          <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6">
            <h3 className="font-semibold text-red-800 mb-2">Problem Statement</h3>
            <p className="text-red-700">
              Urban roads face unpredictable congestion, and existing traffic management systems struggle to adapt in real-time.
            </p>
          </div>
          
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
            <h3 className="font-semibold text-blue-800 mb-2">Objective</h3>
            <p className="text-blue-700">
              Build a Kafka-based streaming pipeline with Hadoop for storing traffic data (e.g., METR-LA, PEMS-BAY). 
              Train a regression model to forecast congestion hotspots and provide real-time congestion heatmaps for city planners.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-green-500">
              <div className="text-2xl mb-3">📊</div>
              <h3 className="font-semibold text-gray-800 mb-2">Real-Time Streaming</h3>
              <p className="text-gray-600 text-sm">Kafka pipeline processes traffic data from METR-LA and PEMS-BAY datasets</p>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-blue-500">
              <div className="text-2xl mb-3">🎯</div>
              <h3 className="font-semibold text-gray-800 mb-2">ML Predictions</h3>
              <p className="text-gray-600 text-sm">Regression models forecast congestion hotspots with high accuracy</p>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-purple-500">
              <div className="text-2xl mb-3">🗺️</div>
              <h3 className="font-semibold text-gray-800 mb-2">City Planning Tools</h3>
              <p className="text-gray-600 text-sm">Interactive heatmaps and analytics for urban traffic management</p>
            </div>
          </div>
        </div>

        <div className="flex gap-4 items-center flex-col sm:flex-row">
          <Link
            className="rounded-full border border-solid border-transparent transition-colors flex items-center justify-center bg-foreground text-background gap-2 hover:bg-[#383838] dark:hover:bg-[#ccc] font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 sm:w-auto"
            href="/dashboard"
          >
            View Dashboard
          </Link>
          <a
            className="rounded-full border border-solid border-black/[.08] dark:border-white/[.145] transition-colors flex items-center justify-center hover:bg-[#f2f2f2] dark:hover:bg-[#1a1a1a] hover:border-transparent font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 w-full sm:w-auto md:w-[158px]"
            href="https://nextjs.org/docs?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read our docs
          </a>
        </div>
      </main>
      <footer className="row-start-3 flex gap-[24px] flex-wrap items-center justify-center">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org/learn?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/file.svg"
            alt="File icon"
            width={16}
            height={16}
          />
          Learn
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://vercel.com/templates?framework=next.js&utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/window.svg"
            alt="Window icon"
            width={16}
            height={16}
          />
          Examples
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/globe.svg"
            alt="Globe icon"
            width={16}
            height={16}
          />
          Go to nextjs.org →
        </a>
      </footer>
    </div>
  );
}

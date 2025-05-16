"use client";
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
// import HeartLogo from '@/components/HeartLogo'

export default function LandingPage() {
  const router = useRouter();

  const handleStart = () => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('clinical_context');
      sessionStorage.removeItem('clinical_question');
      sessionStorage.removeItem('submission_timestamp');
      sessionStorage.removeItem('ai_response');
    }
    router.push('/context');
  };

  return (
    <div className="min-h-screen flex flex-col justify-between text-center bg-white">
      <div className="flex flex-col items-center flex-grow justify-center px-2">
        <div className="mb-4 mt-6">
          <Image src="/Images/HEART.png" alt="HEART logo" width={200} height={200} priority />
        </div>
        <h1 
          className="text-2xl sm:text-3xl font-sans font-bold mb-4 text-primary tracking-wide max-w-2xl mx-auto"
        >
          Hobart Echo Appropriateness Review Tool
        </h1>
        <div className="max-w-2xl mb-6 p-4 sm:p-5 bg-gradient-to-r from-primary/10 to-secondary/10 border-l-4 border-primary rounded-md shadow-md transition-all duration-300 hover:shadow-lg hover:translate-y-[-2px] text-left mx-auto">
          <p className="text-slate-700 leading-relaxed flex">
            <span className="font-bold text-primary mr-2">Important:</span>
            <span>HEART is a clinical guidance tool only. <strong>It does not replace clinical judgment.</strong> Recommendations are based on validated appropriateness criteria, but always discuss with the Cardiology team if there are questions or discrepancies.</span>
          </p>
        </div>
        <button
          onClick={handleStart}
          className="btn btn-primary mb-6 sm:mb-8 px-6 py-2 text-base"
        >
          Start
        </button>
      </div>
      <footer className="mb-6 sm:mb-8 relative">
        <div className="flex justify-center space-x-6 sm:space-x-10">
          <Link 
            href="/about" 
            className="text-primary hover:underline text-base sm:text-lg"
          >
            About
          </Link>
          <Link 
            href="/help" 
            className="text-primary hover:underline text-base sm:text-lg"
          >
            Help
          </Link>
        </div>
        <a
          href="https://cms-cardiologysouth.health.local/icvis"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline absolute right-8 bottom-0 text-base sm:text-lg"
        >
          Spoke to Cardiology?
        </a>
      </footer>
    </div>
  )
} 
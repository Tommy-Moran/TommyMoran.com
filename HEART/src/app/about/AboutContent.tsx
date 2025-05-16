'use client'

import Link from 'next/link'

export default function AboutContent() {
  return (
    <div className="w-full max-w-4xl mx-auto">
      <h1 className="text-2xl sm:text-3xl font-sans font-bold mb-4 text-primary tracking-wide max-w-2xl mx-auto">About HEART</h1>
      
      <div className="bg-gradient-to-r from-blue-50 to-slate-50 shadow-md rounded-lg p-8 mb-6 transition-all duration-300 hover:shadow-lg border border-slate-100">
        <p className="mb-5 text-slate-700 leading-relaxed">
          HEART (Hobart Echo Appropriateness Review Tool) supports clinicians at the Royal Hobart Hospital in reviewing the need and urgency for echocardiograms. The recommendations are based on validated criteria for inpatient echocardiogram appropriateness.
        </p>
        
        <h2 className="text-xl font-semibold mb-3 text-slate-800">The tool helps determine:</h2>
        
        <ul className="mb-5 space-y-2">
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span className="text-slate-700">Whether an echocardiogram is appropriate for common clinical situations requested</span>
          </li>
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span className="text-slate-700">If appropriate, whether it should be performed as an inpatient or outpatient</span>
          </li>
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span className="text-slate-700">The relative urgency of the study</span>
          </li>
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span className="text-slate-700">Recommendations for other investigations or consultations if applicable</span>
          </li>
        </ul>
        
        <div className="mb-5 p-5 bg-gradient-to-r from-blue-100 to-blue-50 border-l-4 border-blue-500 rounded-md shadow-md transition-all duration-300 hover:shadow-lg hover:translate-y-[-2px]">
          <p className="text-slate-700 leading-relaxed flex">
            <span className="font-bold text-blue-700 mr-2">Important:</span> 
            <span>This is only a tool to guide clinicians. The responsibility remains theirs and it does not replace clinical judgment. When in doubt, please speak directly to the Cardiology Team.</span>
          </p>
        </div>
        
        <div className="mb-5 p-5 bg-gradient-to-r from-amber-100 to-amber-50 border-l-4 border-amber-500 rounded-md shadow-md transition-all duration-300 hover:shadow-lg hover:translate-y-[-2px]">
          <p className="text-slate-700 leading-relaxed">
            No patient identifiers (such as URN, name, or date of birth) are required or used. The clinical context submitted uses an AI agent, and as such should be used only to evaluate common clinical scenarios and should not include any identifiable patient details.
          </p>
        </div>
        <div className="mb-5 p-5 bg-gradient-to-r from-green-100 to-green-50 border-l-4 border-green-500 rounded-md shadow-md transition-all duration-300 hover:shadow-lg hover:translate-y-[-2px]">
          <h3 className="font-bold text-green-700 mb-2">Data Safety & Privacy Commitment</h3>
          <ul className="list-disc pl-5 text-slate-700 space-y-2">
            <li>To comply with Australian Privacy Principles (APP), it is important to prioritize transparency and security of patient data. No idenfifiable patient details are required for use while using the clinical context checker.</li>
          </ul>
        </div>
        
        <p className="mb-6 text-slate-700 leading-relaxed">
          For more information, contact the RHH Cardiology Department.
        </p>
        
        <div className="mt-6 p-5 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200 transition-all duration-300 hover:shadow-md">
          <h3 className="font-semibold mb-3 text-slate-800">References:</h3>
          <ul className="space-y-2 text-sm text-slate-600">
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>ACCF/ASE/AHA/ASNC/HFSA/HRS/SCAI/SCCM/SCCT/SCMR 2011 Appropriate Use Criteria for Echocardiography (J Am Soc Echocardiogr. 2011)</span>
            </li>
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>ACC/AATS/AHA/ASE/ASNC/HRS/SCAI/SCCT/SCMR/STS 2019 Appropriate Use Criteria for Multimodality Imaging (JACC. 2019)</span>
            </li>
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>2020 ACC/AHA Valvular Heart Disease Guidelines (JACC. 2021)</span>
            </li>
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>2021 ESC Heart Failure Guidelines (EHJ. 2021)</span>
            </li>
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>Medicare Cardiac Echo Item Numbers (Australia)</span>
            </li>
            <li className="flex items-start">
              <span className="text-slate-400 mr-2">•</span>
              <span>Fonseca R, et al. The Appropriateness and Impact of the Use of Cardiovascular Imaging (BMJ Open. 2016)</span>
            </li>
          </ul>
        </div>
      </div>
      
      <div className="flex justify-center">
        <Link 
          href="/"
          className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white font-medium rounded-md hover:from-blue-700 hover:to-blue-800 transition-all shadow-sm hover:shadow-md"
        >
          Back to Home
        </Link>
      </div>
      <p className="mt-8 text-center text-sm text-gray-500">© SPICY AI 2025. All rights reserved.</p>
    </div>
  )
} 
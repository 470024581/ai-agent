import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FaBrain, FaDatabase, FaGlobe, FaProjectDiagram, FaInfoCircle, FaDownload, FaGithub, FaLinkedin, FaYoutube } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogOverlay, DialogPortal } from '@/components/ui/dialog'

function Header() {
  const { t, i18n } = useTranslation()
  const [showAboutDialog, setShowAboutDialog] = useState(false)

  const handleDownloadResume = async () => {
    try {
      const response = await fetch('/api/v1/download/resume')
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'LiangLong_Resume.pdf'
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } else {
        alert(t('about.resumeDownloadError'))
      }
    } catch (error) {
      console.error('Error downloading resume:', error)
      alert(t('about.resumeDownloadError'))
    }
  }

  return (
    <>
      <header className="border-b border-orange-100 bg-gradient-to-r from-orange-50/50 to-pink-50/50 shadow-sm">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center space-x-4">
            <Link to="/intelligent-analysis" className="flex items-center space-x-2 text-lg font-bold group">
              <FaBrain className="h-7 w-7 text-orange-300 group-hover:text-orange-400 transition-colors" />
              <span className="bg-gradient-to-r from-orange-400 to-pink-400 bg-clip-text text-transparent">{t('smartAIAssistant')}</span>
            </Link>
          </div>

          <nav className="hidden md:flex items-center space-x-8">
            {/* <Link 
              to="/query" 
              className="flex items-center space-x-2 text-sm font-medium transition-all hover:scale-105 group"
            >
              <FaBrain className="h-4 w-4 text-orange-300 group-hover:text-orange-400" />
              <span className="text-gray-600 group-hover:text-orange-400">{t('intelligentQA')}</span>
            </Link>
            */}
            <Link 
              to="/intelligent-analysis" 
              className="flex items-center space-x-2 text-sm font-medium transition-all hover:scale-105 group"
            >
              <FaProjectDiagram className="h-4 w-4 text-blue-300 group-hover:text-blue-400" />
              <span className="text-gray-600 group-hover:text-blue-400">{t('intelligentAnalysis.title')}</span>
            </Link>
            <Link 
              to="/datasources" 
              className="flex items-center space-x-2 text-sm font-medium transition-all hover:scale-105 group"
            >
              <FaDatabase className="h-4 w-4 text-purple-300 group-hover:text-purple-400" />
              <span className="text-gray-600 group-hover:text-purple-400">{t('dataSourceManagement')}</span>
            </Link>
            <button
              onClick={() => setShowAboutDialog(true)}
              className="flex items-center space-x-2 text-sm font-medium transition-all hover:scale-105 group"
            >
              <FaInfoCircle className="h-4 w-4 text-green-300 group-hover:text-green-400" />
              <span className="text-gray-600 group-hover:text-green-400">{t('about.title')}</span>
            </button>
          </nav>

          <div className="flex items-center space-x-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="flex items-center space-x-2 border-orange-200 text-orange-500 hover:bg-orange-50 hover:border-orange-300 transition-all"
                >
                  <FaGlobe className="h-4 w-4" />
                  <span>{t('language')}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="border-orange-100">
                <DropdownMenuItem 
                  onClick={() => i18n.changeLanguage('en')}
                  className={`${i18n.language === 'en' ? 'bg-orange-50 text-orange-600' : ''} hover:bg-orange-50/50`}
                >
                  English
                </DropdownMenuItem>
                <DropdownMenuItem 
                  onClick={() => i18n.changeLanguage('zh')}
                  className={`${i18n.language === 'zh' ? 'bg-orange-50 text-orange-600' : ''} hover:bg-orange-50/50`}
                >
                  中文
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Mobile menu */}
          <div className="md:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="outline" 
                  size="sm"
                  className="border-orange-200 text-orange-500 hover:bg-orange-50"
                >
                  <span className="sr-only">Open menu</span>
                  <FaBrain className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="border-orange-100">
                <DropdownMenuItem asChild className="hover:bg-blue-50/50">
                  <Link to="/intelligent-analysis" className="flex items-center space-x-2">
                    <FaProjectDiagram className="h-4 w-4 text-blue-300" />
                    <span>{t('intelligentAnalysis.title')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild className="hover:bg-purple-50/50">
                  <Link to="/datasources" className="flex items-center space-x-2">
                    <FaDatabase className="h-4 w-4 text-purple-300" />
                    <span>{t('dataSourceManagement')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem 
                  onClick={() => setShowAboutDialog(true)}
                  className="hover:bg-green-50/50"
                >
                  <div className="flex items-center space-x-2">
                    <FaInfoCircle className="h-4 w-4 text-green-300" />
                    <span>{t('about.title')}</span>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* About Project Dialog */}
      <Dialog open={showAboutDialog} onOpenChange={setShowAboutDialog}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent className="max-w-6xl w-[90vw] max-h-[85vh] overflow-y-auto sm:max-w-6xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FaInfoCircle className="h-5 w-5 text-green-500" />
                {t('about.title')}
              </DialogTitle>
              <DialogDescription className="text-gray-600 mt-2">
                {t('systemDescription')}
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-8 mt-6">
              {/* Project Information Section */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-800 border-b pb-2 flex items-center gap-2">
                  <span className="w-1 h-6 bg-blue-500 rounded-full"></span>
                  {t('about.projectInfo.title')}
                </h3>
                
                <div className="space-y-6">
                  <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-4 rounded-lg border border-blue-100">
                    <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                      <span className="text-blue-500">📋</span>
                      {t('about.projectInfo.description.title')}
                    </h4>
                    <p className="text-gray-700 leading-relaxed">
                      {t('about.projectInfo.description.content')}
                    </p>
                  </div>
                  
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                      <span className="text-blue-500">⚡</span>
                      {t('about.projectInfo.features.title')}
                    </h4>
                    <ul className="space-y-2 text-gray-600">
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.langgraph')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.ragRetrieval')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.executionLogs')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.sqlAgent')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.chartGeneration')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.multiModel')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.websocket')}</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></span>
                        <span>{t('about.projectInfo.features.multiDataSource')}</span>
                      </li>
                    </ul>
                  </div>
                  
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                      <span className="text-blue-500">🛠️</span>
                      {t('about.projectInfo.techStack.title')}
                    </h4>
                    <p className="text-gray-600">
                      {t('about.projectInfo.techStack.content')}
                    </p>
                  </div>
                  
                  <div className="flex flex-wrap gap-4 pt-2">
                    <a 
                      href="https://github.com/470024581/ai-agent" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
                    >
                      <FaGithub className="h-4 w-4" />
                      <span>{t('about.projectInfo.links.github')}</span>
                    </a>
                    <a
                      href="https://youtu.be/0t3gfS5ls8U"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors"
                    >
                      <FaYoutube className="h-4 w-4" />
                      <span>{t('about.projectInfo.links.youtube')}</span>
                    </a>
                  </div>
                </div>
              </div>

              {/* Author Information Section */}
              <div className="space-y-4 border-t pt-6">
                <h3 className="text-lg font-semibold text-gray-800 border-b pb-2 flex items-center gap-2">
                  <span className="w-1 h-6 bg-green-500 rounded-full"></span>
                  {t('about.author.title')}
                </h3>
                
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                    <div>
                      <span className="font-medium text-gray-700">{t('about.author.name')}:</span>
                      <span className="ml-2 text-gray-600">{t('about.author.nameValue')}</span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">{t('about.author.email')}:</span>
                      <a href="mailto:lianglongll1990@163.com" className="ml-2 text-blue-600 hover:underline">
                        lianglongll1990@163.com
                      </a>
                    </div>
                  </div>

                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                      <span className="text-green-500">👤</span>
                      {t('about.author.introduction.title')}
                    </h4>
                    <p className="text-gray-600 leading-relaxed">
                      {t('about.author.introduction.content')}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-4">
                    <a 
                      href="https://www.linkedin.com/in/long-liang-27b090292" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors"
                    >
                      <FaLinkedin className="h-4 w-4" />
                      <span>{t('about.author.linkedin')}</span>
                    </a>
                    <button
                      onClick={handleDownloadResume}
                      className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors"
                    >
                      <FaDownload className="h-4 w-4" />
                      <span>{t('about.author.downloadResume')}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </DialogContent>
        </DialogPortal>
      </Dialog>
    </>
  )
}

export default Header 
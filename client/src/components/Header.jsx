import { Link } from 'react-router-dom'
import { FaBrain, FaDatabase, FaGlobe, FaProjectDiagram } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

function Header() {
  const { t, i18n } = useTranslation()

  return (
    <header className="border-b border-orange-100 bg-gradient-to-r from-orange-50/50 to-pink-50/50 shadow-sm">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center space-x-4">
          <Link to="/query" className="flex items-center space-x-2 text-lg font-bold group">
            <FaBrain className="h-7 w-7 text-orange-300 group-hover:text-orange-400 transition-colors" />
            <span className="bg-gradient-to-r from-orange-400 to-pink-400 bg-clip-text text-transparent">{t('smartAIAssistant')}</span>
          </Link>
        </div>

        <nav className="hidden md:flex items-center space-x-8">
          <Link 
            to="/query" 
            className="flex items-center space-x-2 text-sm font-medium transition-all hover:scale-105 group"
          >
            <FaBrain className="h-4 w-4 text-orange-300 group-hover:text-orange-400" />
            <span className="text-gray-600 group-hover:text-orange-400">{t('intelligentQA')}</span>
          </Link>
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
                             <DropdownMenuItem asChild className="hover:bg-orange-50/50">
                  <Link to="/query" className="flex items-center space-x-2">
                    <FaBrain className="h-4 w-4 text-orange-300" />
                    <span>{t('intelligentQA')}</span>
                  </Link>
                </DropdownMenuItem>
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
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}

export default Header 
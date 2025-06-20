import { Navbar, Nav, Container, NavDropdown } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import { FaBrain, FaDatabase } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'

function Header() {
  const { t, i18n } = useTranslation()

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng)
  }

  return (
    <Navbar bg="primary" variant="dark" expand="lg" className="mb-3">
      <Container>
        <Navbar.Brand as={Link} to="/query">
          <FaBrain className="me-2" />
          {t('smartAIAssistant')}
        </Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            <Nav.Link as={Link} to="/query">
              <FaBrain className="me-1" />
              {t('intelligentQA')}
            </Nav.Link>
            <Nav.Link as={Link} to="/datasources">
              <FaDatabase className="me-1" />
              {t('dataSourceManagement')}
            </Nav.Link>
          </Nav>
          <Nav>
            <NavDropdown title={t('language')} id="basic-nav-dropdown">
              <NavDropdown.Item onClick={() => i18n.changeLanguage('en')} active={i18n.language === 'en'}>
                English
              </NavDropdown.Item>
              <NavDropdown.Item onClick={() => i18n.changeLanguage('zh')} active={i18n.language === 'zh'}>
                中文
              </NavDropdown.Item>
            </NavDropdown>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  )
}

export default Header 
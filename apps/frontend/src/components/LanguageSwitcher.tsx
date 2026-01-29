import { useTranslation } from 'react-i18next';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  
  const toggleLanguage = () => {
    const newLang = i18n.language === 'zh-CN' ? 'en-US' : 'zh-CN';
    i18n.changeLanguage(newLang);
  };
  
  return (
    <button 
      onClick={toggleLanguage}
      className="px-3 py-1 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-800"
    >
      {i18n.language === 'zh-CN' ? 'EN' : '中文'}
    </button>
  );
}

"""
지능적 로그인 처리기
"""
import asyncio
import re
from bs4 import BeautifulSoup


class LoginManager:
    """지능적 로그인 폼 탐지 및 처리"""
    
    async def auto_login(self, page, main_url, username, password):
        """자동 로그인 처리"""
        print("로그인 처리 중...")
        
        try:
            await page.goto(main_url)
            await page.wait_for_load_state("networkidle")
            
            # 로그인 폼 자동 탐지
            login_form = await self._detect_login_form(page)
            
            if login_form:
                print(f"로그인 폼 탐지 완료: {login_form}")
                selectors = await self._smart_login(page, login_form, username, password)
                print("로그인 완료")
                return selectors
            else:
                print("로그인 폼을 찾을 수 없습니다.")
                selectors = await self._fallback_login(page, username, password)
                return selectors
            
        except Exception as e:
            print(f"자동 로그인 실패: {e}")
            selectors = await self._fallback_login(page, username, password)
            return selectors
    
    
    async def _detect_login_form(self, page):
        """로그인 폼 지능적 탐지"""
        print("   로그인 폼 탐지 중...")
        
        # HTML 소스 가져오기
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1단계: form 태그 내에서 password 필드 찾기
        forms = soup.find_all('form')
        for form in forms:
            password_input = form.find('input', {'type': 'password'})
            if password_input:
                form_selector = self._generate_form_selector(form)
                if form_selector:
                    return {
                        'type': 'form',
                        'form_selector': form_selector,
                        'method': 'form_submit'
                    }
        
        # 2단계: password 필드가 있는 컨테이너 찾기
        password_inputs = soup.find_all('input', {'type': 'password'})
        if password_inputs:
            for pw_input in password_inputs:
                container = self._find_login_container(pw_input)
                if container:
                    return {
                        'type': 'container',
                        'container_selector': self._generate_element_selector(container),
                        'method': 'field_by_field'
                    }
        
        # 3단계: 로그인 관련 키워드로 컨테이너 찾기
        login_keywords = ['login', 'signin', '로그인', 'member', '회원']
        for keyword in login_keywords:
            elements = soup.find_all(attrs={'class': re.compile(keyword, re.I)})
            elements.extend(soup.find_all(attrs={'id': re.compile(keyword, re.I)}))
            
            for element in elements:
                if self._has_login_fields(element):
                    return {
                        'type': 'keyword_container',
                        'container_selector': self._generate_element_selector(element),
                        'method': 'field_by_field'
                    }
        
        return None
    
    def _generate_form_selector(self, form):
        """form 태그에 대한 CSS 선택자 생성"""
        if form.get('id'):
            return f"#{form['id']}"
        elif form.get('class'):
            classes = ' '.join(form['class'])
            return f"form.{classes.replace(' ', '.')}"
        elif form.get('action'):
            return f"form[action='{form['action']}']"
        else:
            return "form"
    
    def _generate_element_selector(self, element):
        """일반 요소에 대한 CSS 선택자 생성"""
        if element.get('id'):
            return f"#{element['id']}"
        elif element.get('class'):
            classes = ' '.join(element['class'])
            return f"{element.name}.{classes.replace(' ', '.')}"
        else:
            return element.name
    
    def _find_login_container(self, password_input):
        """password 입력 필드의 상위 로그인 컨테이너 찾기"""
        current = password_input.parent
        while current and current.name != 'body':
            # 같은 컨테이너에 텍스트 입력 필드가 있는지 확인
            text_inputs = current.find_all('input', {'type': ['text', 'email']})
            if text_inputs and len(text_inputs) >= 1:
                return current
            current = current.parent
        return None
    
    def _has_login_fields(self, element):
        """해당 요소 내에 로그인 필드들이 있는지 확인"""
        text_inputs = element.find_all('input', {'type': ['text', 'email']})
        password_inputs = element.find_all('input', {'type': 'password'})
        return len(text_inputs) >= 1 and len(password_inputs) >= 1
    
    async def _smart_login(self, page, login_form, username, password):
        """탐지된 로그인 폼으로 스마트 로그인"""
        if login_form['method'] == 'form_submit':
            return await self._form_submit_login(page, login_form, username, password)
        else:
            return await self._field_by_field_login(page, login_form, username, password)
    
    async def _form_submit_login(self, page, login_form, username, password):
        """form submit 방식 로그인"""
        form_selector = login_form['form_selector']
        username_field = await self._find_username_field_in_form(page, form_selector)
        password_field = await self._find_password_field_in_form(page, form_selector)
        btn_selector = await self._find_submit_button_in_form(page, form_selector)
        if username_field and password_field:
            await page.fill(username_field, username)
            await page.fill(password_field, password)
            if btn_selector:
                await page.click(btn_selector)
            else:
                await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            return {"id": username_field, "pw": password_field, "btn": btn_selector}
        return None
    
    async def _field_by_field_login(self, page, login_form, username, password):
        """개별 필드 방식 로그인"""
        container_selector = login_form['container_selector']
        username_field = await self._find_username_field_in_container(page, container_selector)
        password_field = await self._find_password_field_in_container(page, container_selector)
        btn_selector = await self._find_login_button_in_container(page, container_selector)
        if username_field and password_field:
            await page.fill(username_field, username)
            await page.fill(password_field, password)
            if btn_selector:
                await page.click(btn_selector)
            else:
                await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            return {"id": username_field, "pw": password_field, "btn": btn_selector}
        return None
    
    async def _find_username_field_in_form(self, page, form_selector):
        """form 내에서 사용자명 필드 찾기"""
        selectors = [
            f"{form_selector} input[type='text']",
            f"{form_selector} input[type='email']",
            f"{form_selector} input[name*='id']",
            f"{form_selector} input[name*='user']",
            f"{form_selector} input[name*='login']",
            f"{form_selector} input[placeholder*='아이디']",
            f"{form_selector} input[placeholder*='ID']"
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return selector
            except:
                continue
        return None
    
    async def _find_password_field_in_form(self, page, form_selector):
        """form 내에서 비밀번호 필드 찾기"""
        return f"{form_selector} input[type='password']"
    
    async def _find_submit_button_in_form(self, page, form_selector):
        """form 내에서 submit 버튼 찾기"""
        selectors = [
            f"{form_selector} button[type='submit']",
            f"{form_selector} input[type='submit']",
            f"{form_selector} button",
            f"{form_selector} input[type='button']"
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return selector
            except:
                continue
        return None
    
    async def _find_username_field_in_container(self, page, container_selector):
        """컨테이너 내에서 사용자명 필드 찾기"""
        selectors = [
            f"{container_selector} input[type='text']",
            f"{container_selector} input[type='email']",
            f"{container_selector} input[name*='id']",
            f"{container_selector} input[name*='user']",
            f"{container_selector} input[name*='login']",
            f"{container_selector} input[placeholder*='아이디']",
            f"{container_selector} input[placeholder*='ID']"
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return selector
            except:
                continue
        return None
    
    async def _find_password_field_in_container(self, page, container_selector):
        """컨테이너 내에서 비밀번호 필드 찾기"""
        return f"{container_selector} input[type='password']"
    
    async def _find_login_button_in_container(self, page, container_selector):
        """컨테이너 내에서 로그인 버튼 찾기"""
        selectors = [
            f"{container_selector} button:has-text('로그인')",
            f"{container_selector} input[value*='로그인']",
            f"{container_selector} button:has-text('LOGIN')",
            f"{container_selector} input[value*='LOGIN']",
            f"{container_selector} button[type='submit']",
            f"{container_selector} input[type='submit']",
            f"{container_selector} button",
            f"{container_selector} input[type='button']"
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return selector
            except:
                continue
        return None
    
    async def _fallback_login(self, page, username, password):
        """폴백 로그인 방식"""
        print("폴백 모드: 기본 선택자로 로그인 시도...")
        return await self._try_basic_login(page, username, password)
    
    async def _try_basic_login(self, page, username, password):
        """기본 로그인 시도"""
        try:
            id_selectors = [
                "#id", "#username", "#user_id", "#login_id",
                "input[name='id']", "input[name='username']", 
                "input[type='text']", "input[placeholder*='아이디']"
            ]
            username_filled = False
            used_id_selector = None
            for selector in id_selectors:
                try:
                    await page.fill(selector, username)
                    username_filled = True
                    used_id_selector = selector
                    break
                except:
                    continue
            pw_selectors = [
                "#password", "#passwd", "#pw", 
                "input[name='password']", "input[type='password']"
            ]
            password_filled = False
            used_pw_selector = None
            for selector in pw_selectors:
                try:
                    await page.fill(selector, password)
                    password_filled = True
                    used_pw_selector = selector
                    break
                except:
                    continue
            if not username_filled or not password_filled:
                print("로그인 필드를 찾을 수 없습니다.")
                print("수동으로 로그인 후 Enter를 눌러주세요...")
                input()
                return None
            login_selectors = [
                "button[type='submit']", "input[type='submit']",
                ".login-btn", ".btn-login", "#login-btn",
                "button:has-text('로그인')", "input[value*='로그인']"
            ]
            button_clicked = False
            used_btn_selector = None
            for selector in login_selectors:
                try:
                    await page.click(selector)
                    button_clicked = True
                    used_btn_selector = selector
                    await page.wait_for_load_state("networkidle")
                    break
                except:
                    continue
            if not button_clicked:
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle")
            print("기본 로그인 완료")
            return {"id": used_id_selector, "pw": used_pw_selector, "btn": used_btn_selector}
        except Exception as e:
            print(f"기본 로그인 실패: {e}")
            print("수동으로 로그인 후 Enter를 눌러주세요...")
            input()
            return None

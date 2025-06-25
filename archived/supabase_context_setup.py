"""
Supabase 맥락 저장 시스템 (직접 API 사용)
"""
import json
import requests
from datetime import datetime
import sys
import io

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class SupabaseContextManager:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.supabase.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
    def test_connection(self):
        """Supabase 연결 테스트"""
        try:
            response = requests.get(
                f"{self.base_url}/projects",
                headers=self.headers
            )
            if response.status_code == 200:
                projects = response.json()
                print(f"✅ Supabase 연결 성공! 프로젝트 {len(projects)}개 발견")
                for project in projects:
                    print(f"  📂 {project['name']} (ID: {project['id']})")
                    print(f"     지역: {project['region']}")
                    print(f"     상태: {project['status']}")
                    print()
                return projects
            else:
                print(f"❌ 연결 실패: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return None
    
    def get_project_url(self, project_id: str):
        """프로젝트 URL 확인"""
        try:
            response = requests.get(
                f"{self.base_url}/projects/{project_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                project = response.json()
                return project.get('endpoint')
            return None
        except:
            return None
    
    def execute_sql_via_api(self, project_ref: str, query: str):
        """프로젝트에서 SQL 실행 (REST API 사용)"""
        # Supabase 프로젝트의 REST API 엔드포인트
        project_url = f"https://{project_ref}.supabase.co"
        
        # 실제로는 Supabase 클라이언트 라이브러리나 
        # 프로젝트별 API 키가 필요합니다
        print(f"📋 다음 SQL을 Supabase 대시보드에서 실행해주세요:")
        print("=" * 60)
        print(query)
        print("=" * 60)
        
    def prepare_context_sql(self):
        """맥락 저장용 테이블 생성 SQL"""
        sql = """
-- 키드짐 크롤링 프로젝트 맥락 저장 테이블들

-- 1. 작업 맥락 메인 테이블
CREATE TABLE IF NOT EXISTS kidgym_work_context (
    id SERIAL PRIMARY KEY,
    project_name TEXT NOT NULL DEFAULT '키드짐 크롤링 시스템 개선',
    current_phase TEXT NOT NULL,
    completed_tasks JSONB DEFAULT '[]'::jsonb,
    current_task JSONB DEFAULT '{}'::jsonb,
    next_tasks JSONB DEFAULT '[]'::jsonb,
    technical_details JSONB DEFAULT '{}'::jsonb,
    file_changes JSONB DEFAULT '{}'::jsonb,
    performance_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. 작업 히스토리 테이블
CREATE TABLE IF NOT EXISTS kidgym_task_history (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    summary TEXT,
    implementation_steps JSONB DEFAULT '[]'::jsonb,
    technical_notes JSONB DEFAULT '{}'::jsonb,
    file_changes JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. 기술적 이슈 추적 테이블
CREATE TABLE IF NOT EXISTS kidgym_technical_issues (
    id SERIAL PRIMARY KEY,
    issue_type TEXT NOT NULL,
    description TEXT NOT NULL,
    solution TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    related_files JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_work_context_phase ON kidgym_work_context(current_phase);
CREATE INDEX IF NOT EXISTS idx_task_history_status ON kidgym_task_history(status);
CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON kidgym_task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_technical_issues_status ON kidgym_technical_issues(status);

-- Row Level Security 활성화 (선택사항)
ALTER TABLE kidgym_work_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE kidgym_task_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE kidgym_technical_issues ENABLE ROW LEVEL SECURITY;
"""
        return sql
    
    def prepare_context_data(self):
        """로컬 맥락을 Supabase 형태로 변환"""
        try:
            with open('context_database.json', 'r', encoding='utf-8') as f:
                context = json.load(f)
            
            # 메인 맥락 데이터
            main_context = {
                "project_name": context['project_info']['name'],
                "current_phase": context['project_info']['current_phase'],
                "completed_tasks": context['completed_tasks'],
                "current_task": context['current_task'],
                "next_tasks": context['next_tasks'],
                "technical_details": context['technical_context'],
                "file_changes": context['file_changes'],
                "performance_metrics": context.get('performance_metrics', {}),
                "updated_at": datetime.now().isoformat()
            }
            
            # 작업 히스토리 데이터
            task_history = []
            for task in context['completed_tasks']:
                task_history.append({
                    "task_id": task['id'],
                    "task_name": task['name'],
                    "status": task['status'],
                    "completed_at": task.get('completion_date'),
                    "summary": task.get('summary', ''),
                    "created_at": datetime.now().isoformat()
                })
            
            # 현재 작업도 히스토리에 추가
            if context['current_task']:
                task_history.append({
                    "task_id": context['current_task']['id'],
                    "task_name": context['current_task']['name'],
                    "status": context['current_task']['status'],
                    "started_at": context['current_task'].get('started_date'),
                    "implementation_steps": context['current_task'].get('implementation_steps', []),
                    "created_at": datetime.now().isoformat()
                })
            
            return main_context, task_history
            
        except Exception as e:
            print(f"❌ 맥락 데이터 준비 실패: {e}")
            return None, None
    
    def generate_insert_sql(self, main_context, task_history):
        """Supabase 삽입용 SQL 생성"""
        
        # JSON 데이터를 SQL 문자열로 변환
        def json_to_sql(data):
            return json.dumps(data, ensure_ascii=False).replace("'", "''")
        
        # 메인 맥락 삽입 SQL
        main_sql = f"""
-- 메인 맥락 데이터 삽입 (기존 데이터가 있으면 업데이트)
INSERT INTO kidgym_work_context (
    project_name, current_phase, completed_tasks, current_task, 
    next_tasks, technical_details, file_changes, performance_metrics, updated_at
) VALUES (
    '{main_context["project_name"]}',
    '{main_context["current_phase"]}',
    '{json_to_sql(main_context["completed_tasks"])}'::jsonb,
    '{json_to_sql(main_context["current_task"])}'::jsonb,
    '{json_to_sql(main_context["next_tasks"])}'::jsonb,
    '{json_to_sql(main_context["technical_details"])}'::jsonb,
    '{json_to_sql(main_context["file_changes"])}'::jsonb,
    '{json_to_sql(main_context["performance_metrics"])}'::jsonb,
    NOW()
) ON CONFLICT (id) DO UPDATE SET
    current_phase = EXCLUDED.current_phase,
    completed_tasks = EXCLUDED.completed_tasks,
    current_task = EXCLUDED.current_task,
    next_tasks = EXCLUDED.next_tasks,
    technical_details = EXCLUDED.technical_details,
    file_changes = EXCLUDED.file_changes,
    performance_metrics = EXCLUDED.performance_metrics,
    updated_at = EXCLUDED.updated_at;
"""
        
        # 작업 히스토리 삽입 SQL
        history_sql = "-- 작업 히스토리 데이터 삽입\n"
        for task in task_history:
            history_sql += f"""
INSERT INTO kidgym_task_history (
    task_id, task_name, status, started_at, completed_at, summary, implementation_steps
) VALUES (
    '{task["task_id"]}',
    '{task["task_name"]}',
    '{task["status"]}',
    {f"'{task.get('started_at')}'" if task.get('started_at') else 'NULL'},
    {f"'{task.get('completed_at')}'" if task.get('completed_at') else 'NULL'},
    '{task.get("summary", "")}',
    '{json_to_sql(task.get("implementation_steps", []))}'::jsonb
) ON CONFLICT (task_id) DO UPDATE SET
    status = EXCLUDED.status,
    completed_at = EXCLUDED.completed_at,
    summary = EXCLUDED.summary;
"""
        
        return main_sql + "\n" + history_sql

if __name__ == "__main__":
    print("🚀 Supabase 맥락 저장 시스템 시작")
    print("=" * 60)
    
    # 토큰으로 연결
    token = "sbp_aacb4e6f6633eb3baf8aa71ce3241a8bdfd79e8e"
    supabase = SupabaseContextManager(token)
    
    # 1. 연결 테스트
    projects = supabase.test_connection()
    
    if projects:
        print("\n📋 단계 1: 테이블 생성 SQL")
        sql_create = supabase.prepare_context_sql()
        print(sql_create)
        
        print("\n📋 단계 2: 맥락 데이터 준비")
        main_context, task_history = supabase.prepare_context_data()
        
        if main_context and task_history:
            print("✅ 맥락 데이터 준비 완료")
            print(f"   프로젝트: {main_context['project_name']}")
            print(f"   현재 단계: {main_context['current_phase']}")
            print(f"   완료 작업: {len(main_context['completed_tasks'])}개")
            print(f"   히스토리: {len(task_history)}개 작업")
            
            print("\n📋 단계 3: 데이터 삽입 SQL")
            sql_insert = supabase.generate_insert_sql(main_context, task_history)
            
            print("\n🎯 Supabase 대시보드에서 실행할 SQL:")
            print("=" * 60)
            print("-- 1단계: 테이블 생성")
            print(sql_create)
            print("\n-- 2단계: 데이터 삽입")
            print(sql_insert)
            print("=" * 60)

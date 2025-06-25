"""
Supabase 맥락 동기화 스크립트
로컬 JSON 맥락을 Supabase 데이터베이스와 동기화
"""
import json
import requests
from datetime import datetime
from typing import Dict, Any

class SupabaseContextSync:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.supabase.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.project_id = None
        
    def list_projects(self):
        """Supabase 프로젝트 목록 조회"""
        try:
            response = requests.get(
                f"{self.base_url}/projects",
                headers=self.headers
            )
            if response.status_code == 200:
                projects = response.json()
                print(f"✅ 프로젝트 {len(projects)}개 발견:")
                for project in projects:
                    print(f"  - {project['name']} ({project['id']})")
                return projects
            else:
                print(f"❌ 프로젝트 조회 실패: {response.status_code}")
                print(response.text)
                return []
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return []
    
    def create_project(self, name: str, organization_id: str):
        """새 Supabase 프로젝트 생성"""
        try:
            data = {
                "name": name,
                "organization_id": organization_id,
                "plan": "free",
                "region": "ap-northeast-1"  # 서울과 가까운 도쿄 리전
            }
            
            response = requests.post(
                f"{self.base_url}/projects",
                headers=self.headers,
                json=data
            )
            
            if response.status_code in [200, 201]:
                project = response.json()
                self.project_id = project['id']
                print(f"✅ 프로젝트 생성 성공: {project['name']}")
                print(f"   프로젝트 ID: {project['id']}")
                return project
            else:
                print(f"❌ 프로젝트 생성 실패: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return None
    
    def setup_context_tables(self, project_id: str):
        """맥락 저장용 테이블 생성"""
        # 실제 테이블 생성은 Supabase 대시보드에서 수행하거나
        # 프로젝트 초기화 후 SQL을 실행해야 함
        print(f"📋 프로젝트 {project_id}에서 다음 테이블을 생성해주세요:")
        
        sql_script = """
-- 작업 맥락 테이블
CREATE TABLE work_context (
    id SERIAL PRIMARY KEY,
    project_name TEXT NOT NULL,
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

-- 작업 히스토리 테이블  
CREATE TABLE task_history (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    summary TEXT,
    technical_notes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX idx_work_context_project ON work_context(project_name);
CREATE INDEX idx_task_history_task_id ON task_history(task_id);
CREATE INDEX idx_task_history_status ON task_history(status);
"""
        
        print(sql_script)
        return sql_script
    
    def sync_local_context(self, local_context_file: str = "context_database.json"):
        """로컬 맥락을 Supabase에 동기화"""
        try:
            with open(local_context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            print("📤 로컬 맥락 데이터를 Supabase에 동기화 중...")
            
            # 맥락 데이터 구조화
            sync_data = {
                "project_name": context_data['project_info']['name'],
                "current_phase": context_data['project_info']['current_phase'],
                "completed_tasks": context_data['completed_tasks'],
                "current_task": context_data['current_task'],
                "next_tasks": context_data['next_tasks'],
                "technical_details": context_data['technical_context'],
                "file_changes": context_data['file_changes'],
                "performance_metrics": context_data.get('performance_metrics', {}),
                "updated_at": datetime.now().isoformat()
            }
            
            print("✅ 동기화 데이터 준비 완료")
            print(f"   프로젝트: {sync_data['project_name']}")
            print(f"   현재 단계: {sync_data['current_phase']}")
            print(f"   완료 작업: {len(sync_data['completed_tasks'])}개")
            print(f"   대기 작업: {len(sync_data['next_tasks'])}개")
            
            # 실제 업로드는 프로젝트 및 테이블 생성 후 가능
            return sync_data
            
        except Exception as e:
            print(f"❌ 동기화 실패: {e}")
            return None

if __name__ == "__main__":
    import sys
    import io
    
    # Windows 콘솔 인코딩 설정
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Supabase 맥락 동기화 시스템")
    print("=" * 60)
    
    # 토큰으로 초기화
    token = "sbp_aacb4e6f6633eb3baf8aa71ce3241a8bdfd79e8e"
    sync = SupabaseContextSync(token)
    
    # 프로젝트 목록 조회
    projects = sync.list_projects()
    
    # 로컬 맥락 동기화 준비
    sync_data = sync.sync_local_context()
    
    if sync_data:
        print("\n🎯 다음 단계:")
        print("1. Supabase 대시보드에서 프로젝트 생성")
        print("2. 위의 SQL 스크립트로 테이블 생성")
        print("3. 맥락 데이터 업로드 실행")

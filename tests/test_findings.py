import asyncio
import os
from analysis.static_analyzer import StaticAnalyzer
from analysis.security_scanner import SecurityScanner

async def run():
    session_dir = "data/uploads/test_e2e_session/extracted"
    if not os.path.exists(session_dir):
        print(f"Session dir not found: {session_dir}")
        return
        
    print("Running static analyzer...")
    sa = StaticAnalyzer(session_dir)
    sa_res = sa.analyze_repo("test")
    print(f"Static findings: {len(sa_res)}")
    
    print("Running security scanner...")
    ss = SecurityScanner(session_dir)
    ss_res = ss.analyze_repo()
    print(f"Security findings: {len(ss_res)}")
    
    total = len(sa_res) + len(ss_res)
    print(f"Total findings: {total}")
    print(f"Estimated time with sequential LLM calls: {total * 2} seconds")

if __name__ == "__main__":
    asyncio.run(run())

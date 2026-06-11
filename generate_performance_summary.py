#!/usr/bin/env python3
"""
性能统计汇总脚本
用于汇总ASR、LLM、TTS各环节的耗时，并生成Excel报告
"""

import os
import csv
import pandas as pd
from datetime import datetime


def generate_performance_summary():
    """
    生成性能统计汇总报告
    """
    # 检查性能日志文件是否存在
    csv_file = "performance_log.csv"
    detailed_csv_file = "performance_log_detailed.csv"
    
    if not os.path.exists(csv_file):
        print(f"警告: 找不到基本性能日志文件 {csv_file}")
        return
    
    if not os.path.exists(detailed_csv_file):
        print(f"警告: 找不到详细性能日志文件 {detailed_csv_file}")
        return
    
    # 生成汇总报告
    summary_file = "performance_summary_report.xlsx"
    
    try:
        # 读取基本性能数据
        df_basic = pd.read_csv(csv_file)
        df_basic['timestamp'] = pd.to_datetime(df_basic['timestamp'])
        
        # 读取详细性能数据
        df_detailed = pd.read_csv(detailed_csv_file)
        df_detailed['timestamp'] = pd.to_datetime(df_detailed['timestamp'])
        
        # 创建Excel写入器
        with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
            # 写入基本性能数据
            df_basic.to_excel(writer, sheet_name='Basic Performance', index=False)
            
            # 写入详细性能数据
            df_detailed.to_excel(writer, sheet_name='Detailed Performance', index=False)
            
            # 创建统计摘要
            summary_data = []
            modules = ['asr_time', 'llm_time', 'tts_time']
            for module in modules:
                if module in df_basic.columns:
                    summary_data.append({
                        'Module': module.replace('_time', '').upper(),
                        'Count': df_basic[module].count(),
                        'Average (seconds)': df_basic[module].mean(),
                        'Min (seconds)': df_basic[module].min(),
                        'Max (seconds)': df_basic[module].max(),
                        'Std Deviation': df_basic[module].std()
                    })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary Statistics', index=False)
            
            # 按小时统计
            df_basic['hour'] = df_basic['timestamp'].dt.hour
            hourly_stats = df_basic.groupby('hour')[['asr_time', 'llm_time', 'tts_time']].mean()
            hourly_stats.to_excel(writer, sheet_name='Hourly Averages')
            
            # 总耗时统计
            if 'total_time' in df_basic.columns:
                total_stats = {
                    'Count': df_basic['total_time'].count(),
                    'Average (seconds)': df_basic['total_time'].mean(),
                    'Min (seconds)': df_basic['total_time'].min(),
                    'Max (seconds)': df_basic['total_time'].max(),
                    'Std Deviation': df_basic['total_time'].std()
                }
                total_df = pd.DataFrame([total_stats])
                total_df.to_excel(writer, sheet_name='Total Time Statistics', index=False)
        
        print(f"性能统计汇总报告已生成: {summary_file}")
        
    except Exception as e:
        print(f"生成性能统计汇总报告时出错: {str(e)}")


def print_latest_performance():
    """
    打印最新的性能数据
    """
    csv_file = "performance_log.csv"
    
    if not os.path.exists(csv_file):
        print(f"找不到性能日志文件 {csv_file}")
        return
    
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 获取最新的记录
        latest_record = df.iloc[-1]
        
        print("\n最新性能数据:")
        print(f"时间: {latest_record['timestamp']}")
        print(f"ASR耗时: {latest_record.get('asr_time', 'N/A')} 秒")
        print(f"LLM耗时: {latest_record.get('llm_time', 'N/A')} 秒")
        print(f"TTS耗时: {latest_record.get('tts_time', 'N/A')} 秒")
        print(f"总耗时: {latest_record.get('total_time', 'N/A')} 秒")
        
    except Exception as e:
        print(f"读取最新性能数据时出错: {str(e)}")


if __name__ == "__main__":
    print("开始生成性能统计汇总报告...")
    generate_performance_summary()
    print_latest_performance()
    print("完成!")
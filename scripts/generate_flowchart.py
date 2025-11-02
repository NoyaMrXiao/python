"""
根據需求文檔生成用戶流程圖
使用 matplotlib 和 networkx 來可視化流程圖
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# 設置中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

def create_flowchart():
    """創建用戶流程圖"""
    fig, ax = plt.subplots(1, 1, figsize=(20, 24))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # 定義節點位置和樣式
    nodes = {}
    y_positions = [11.5, 10.5, 9, 7.5, 6, 4.5, 3, 1.5]
    
    # 第一層：開始和登錄
    nodes['start'] = {'pos': (5, 11.5), 'text': '用戶打開應用', 'style': 'ellipse', 'color': '#e1f5ff'}
    nodes['login'] = {'pos': (5, 10.5), 'text': '登錄/註冊', 'style': 'diamond', 'color': '#ffe1e1'}
    nodes['register'] = {'pos': (3, 9.5), 'text': '註冊頁面\n填寫註冊信息', 'style': 'rect', 'color': '#f0f0f0'}
    nodes['login_page'] = {'pos': (7, 9.5), 'text': '登錄頁面\n輸入登錄信息', 'style': 'rect', 'color': '#f0f0f0'}
    nodes['auth_success'] = {'pos': (5, 9), 'text': '認證成功', 'style': 'rect', 'color': '#d4edda'}
    
    # 第二層：首頁
    nodes['homepage'] = {'pos': (5, 7.5), 'text': '首頁\nHomepage', 'style': 'rect', 'color': '#fff4e1'}
    
    # 第三層：主要功能模塊
    x_main = [1, 3, 5, 7, 9]
    modules = [
        ('comp_list', '比賽信息\nCompetition Listing'),
        ('showcase', '展示中心\nShowcase Hub'),
        ('profile', '個人資料\nProfile'),
        ('journal', '日誌/通知\nJournal'),
        ('help', '幫助與資源\nHelp & Resources')
    ]
    for i, (key, text) in enumerate(modules):
        nodes[key] = {'pos': (x_main[i], 6), 'text': text, 'style': 'rect', 'color': '#e8f4f8'}
    
    # 第四層：子功能
    # 比賽信息子功能
    nodes['comp_details'] = {'pos': (0.5, 4.5), 'text': '比賽詳情\nCompetition Details', 'style': 'rect', 'color': '#ffffff'}
    nodes['judging_panel'] = {'pos': (1, 4.5), 'text': '評審團信息\nJudging Panel', 'style': 'rect', 'color': '#ffffff'}
    nodes['submission'] = {'pos': (1.5, 4.5), 'text': '提交作品\nSubmission Portal', 'style': 'rect', 'color': '#ffffff'}
    
    # 展示中心子功能
    nodes['portfolio'] = {'pos': (2.5, 4.5), 'text': '作品展示\nPortfolio', 'style': 'rect', 'color': '#ffffff'}
    nodes['curated'] = {'pos': (3, 4.5), 'text': '精選內容\nCurated Content', 'style': 'rect', 'color': '#ffffff'}
    nodes['friends_rec'] = {'pos': (3.5, 4.5), 'text': '朋友推薦\nFriends\' Recommendation', 'style': 'rect', 'color': '#ffffff'}
    
    # 個人資料子功能
    nodes['friends_hub'] = {'pos': (4.5, 4.5), 'text': '好友中心\nFriends\' Hub', 'style': 'rect', 'color': '#ffffff'}
    nodes['messages'] = {'pos': (5, 4.5), 'text': '消息中心\nMessages', 'style': 'rect', 'color': '#ffffff'}
    nodes['growth'] = {'pos': (5.5, 4.5), 'text': '個人成長數據\nPersonal Growth\nEngagement Stats', 'style': 'rect', 'color': '#ffffff'}
    
    # 日誌子功能
    nodes['press'] = {'pos': (6.5, 4.5), 'text': '媒體報導\nPress', 'style': 'rect', 'color': '#ffffff'}
    nodes['interviews'] = {'pos': (7, 4.5), 'text': '訪談內容\nInterviews', 'style': 'rect', 'color': '#ffffff'}
    nodes['social'] = {'pos': (7.5, 4.5), 'text': '社交媒體\nSocial Media', 'style': 'rect', 'color': '#ffffff'}
    
    # 幫助子功能
    nodes['bio'] = {'pos': (8.5, 4.5), 'text': '關於我們\nBio', 'style': 'rect', 'color': '#ffffff'}
    nodes['library'] = {'pos': (9, 4.5), 'text': '資源庫\nLibrary', 'style': 'rect', 'color': '#ffffff'}
    nodes['help_notif'] = {'pos': (9.5, 4.5), 'text': '幫助通知\nNotification & Updates', 'style': 'rect', 'color': '#ffffff'}
    
    # 繪製節點
    for key, node in nodes.items():
        x, y = node['pos']
        text = node['text']
        color = node['color']
        
        if node['style'] == 'ellipse':
            # 橢圓
            circle = plt.Circle((x, y), 0.4, color=color, ec='black', linewidth=2, zorder=3)
            ax.add_patch(circle)
            ax.text(x, y, text, ha='center', va='center', fontsize=8, weight='bold', zorder=4)
        elif node['style'] == 'diamond':
            # 菱形
            diamond = mpatches.RegularPolygon((x, y), 4, radius=0.5, 
                                             orientation=np.pi/4, 
                                             facecolor=color, 
                                             edgecolor='black', 
                                             linewidth=2, zorder=3)
            ax.add_patch(diamond)
            ax.text(x, y, text, ha='center', va='center', fontsize=8, weight='bold', zorder=4)
        else:
            # 矩形
            width, height = 0.8, 0.6
            if len(text.split('\n')) > 2:
                height = 0.8
            rect = FancyBboxPatch((x-width/2, y-height/2), width, height,
                                 boxstyle="round,pad=0.05",
                                 facecolor=color,
                                 edgecolor='black',
                                 linewidth=1.5,
                                 zorder=3)
            ax.add_patch(rect)
            ax.text(x, y, text, ha='center', va='center', fontsize=7, zorder=4)
    
    # 繪製箭頭連接
    connections = [
        ('start', 'login'),
        ('login', 'register'),
        ('login', 'login_page'),
        ('register', 'auth_success'),
        ('login_page', 'auth_success'),
        ('auth_success', 'homepage'),
        ('homepage', 'comp_list'),
        ('homepage', 'showcase'),
        ('homepage', 'profile'),
        ('homepage', 'journal'),
        ('homepage', 'help'),
        ('comp_list', 'comp_details'),
        ('comp_list', 'judging_panel'),
        ('comp_list', 'submission'),
        ('showcase', 'portfolio'),
        ('showcase', 'curated'),
        ('showcase', 'friends_rec'),
        ('profile', 'friends_hub'),
        ('profile', 'messages'),
        ('profile', 'growth'),
        ('journal', 'press'),
        ('journal', 'interviews'),
        ('journal', 'social'),
        ('help', 'bio'),
        ('help', 'library'),
        ('help', 'help_notif'),
    ]
    
    for start_key, end_key in connections:
        start_pos = nodes[start_key]['pos']
        end_pos = nodes[end_key]['pos']
        
        # 計算箭頭方向
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        
        # 調整起始和結束位置（考慮節點大小）
        if nodes[start_key]['style'] == 'ellipse':
            r = 0.4
        elif nodes[start_key]['style'] == 'diamond':
            r = 0.5
        else:
            r = 0.4
        
        if nodes[end_key]['style'] == 'ellipse':
            r_end = 0.4
        elif nodes[end_key]['style'] == 'diamond':
            r_end = 0.5
        else:
            r_end = 0.4
        
        # 標準化方向向量
        length = np.sqrt(dx**2 + dy**2)
        if length > 0:
            dx_norm = dx / length
            dy_norm = dy / length
            
            start_adj = (start_pos[0] + dx_norm * r, start_pos[1] + dy_norm * r)
            end_adj = (end_pos[0] - dx_norm * r_end, end_pos[1] - dy_norm * r_end)
            
            arrow = FancyArrowPatch(start_adj, end_adj,
                                   arrowstyle='->',
                                   mutation_scale=20,
                                   linewidth=2,
                                   color='#666666',
                                   zorder=2)
            ax.add_patch(arrow)
    
    # 添加標題
    ax.text(5, 12, 'Web/Mobile 應用用戶流程圖', 
           ha='center', va='bottom', fontsize=16, weight='bold')
    
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'outputs')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'user_flowchart.png')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"流程图已生成: {output_file}")
    plt.show()

if __name__ == "__main__":
    create_flowchart()


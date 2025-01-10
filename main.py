import sys
import subprocess
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox, QFileDialog, QMessageBox, QInputDialog, QListWidget
)
from PySide6.QtCore import QThread, Signal
from qt_material import apply_stylesheet


class ADBCommandThread(QThread):
    """用于在后台执行ADB命令的线程"""
    command_output = Signal(str)  # 用于发送命令执行结果的信号

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            # 使用相对路径
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')  # 假设 adb.exe 在 adb 子目录
            result = subprocess.run(
                f"{adb_path} {self.command}",
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            )
            self.command_output.emit(result.stdout)  # 发送命令输出
        except Exception as e:
            self.command_output.emit(f"执行命令时出错: {str(e)}")


class FastbootCommandThread(QThread):
    """用于在后台执行Fastboot命令的线程"""
    command_output = Signal(str)  # 用于发送命令执行结果的信号

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            # 使用相对路径
            fastboot_path = os.path.join(os.path.dirname(__file__), 'adb', 'fastboot.exe')  # 假设 fastboot.exe 在 adb 子目录
            result = subprocess.run(
                f"{fastboot_path} {self.command}",
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            )
            self.command_output.emit(result.stdout)  # 发送命令输出
        except Exception as e:
            self.command_output.emit(f"执行命令时出错: {str(e)}")


class SeaScript:
    def __init__(self, device=None):
        """
        初始化SeaScript解析器
        :param device: 当前选择的设备
        """
        self.variables = {}  # 存储变量
        self.device = device  # 当前选择的设备

    def parse_script(self, file_path):
        """
        解析SeaScript脚本文件
        :param file_path: 脚本文件路径
        :return: 解析后的命令列表
        """
        commands = []
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        in_loop = False
        loop_count = 0
        loop_commands = []
        self.variables = {'device': self.device}  # 自动设置 device 变量
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # 跳过注释和空行

            if in_loop:
                if line == 'endloop':
                    for _ in range(loop_count):
                        commands.extend(loop_commands)
                    in_loop = False
                    loop_commands = []
                else:
                    loop_commands.append(self.replace_variables(line))
                continue

            if line.startswith('device'):
                self.device = line.split(' ')[1]
                continue

            if line.startswith('echo'):
                self.output_display.append(line[4:].strip() + '\n')
                print(line[4:].strip())
                QMessageBox.information(self, 'lication', line[4:].strip())
            if line.startswith('set'):
                parts = line.split(' ')
                if len(parts) >= 3:
                    self.variables[parts[1]] = ' '.join(parts[2:])
                continue

            if line.startswith('if'):
                condition = line[3:].strip()
                var_name, value = condition.split('==')
                var_name = var_name.strip()
                value = value.strip()
                if self.variables.get(var_name) != value:
                    continue  # 条件不满足，跳过后续命令直到 endif
                continue

            if line == 'endif':
                continue  # 结束条件判断

            if line.startswith('loop'):
                loop_count = int(line.split(' ')[1])
                in_loop = True
                continue

            # 替换变量并添加到命令列表
            commands.append(self.replace_variables(line))

        return commands

    def replace_variables(self, line):
        """
        替换命令中的变量
        :param line: 原始命令
        :return: 替换变量后的命令
        """
        for var_name, var_value in self.variables.items():
            line = line.replace(f'${{{var_name}}}', var_value)
        return line


class FileManager(QWidget):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.initUI()

    def initUI(self):
        self.setWindowTitle('文件管理器')
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        # 路径显示
        self.path_label = QLabel('当前路径: /sdcard')
        layout.addWidget(self.path_label)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.navigate_to)
        layout.addWidget(self.file_list)

        # 返回上一级按钮
        self.back_button = QPushButton('返回上一级')
        self.back_button.clicked.connect(self.navigate_up)
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.current_path = '/sdcard'
        self.refresh_file_list()

    def refresh_file_list(self):
        """刷新文件列表"""
        self.file_list.clear()
        try:
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')
            result = subprocess.run(
                [adb_path, '-s', self.device, 'shell', 'ls', '-1', self.current_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            files = result.stdout.splitlines()
            for file in files:
                if file:  # 确保文件名不为空
                    self.file_list.addItem(file)
        except Exception as e:
            QMessageBox.warning(self, '错误', f"无法获取文件列表: {str(e)}")

    def navigate_to(self, item):
        """导航到选定的目录或处理文件打开"""
        selected_item = item.text()
        new_path = self.current_path + '/' + selected_item  # 使用字符串拼接

        try:
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')
            # 使用 cat 命令检查是否为文件，并设置超时
            try:
                result = subprocess.run(
                    [adb_path, '-s', self.device, 'shell', 'cat', new_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=2  # 设置超时为 2 秒
                )
                if "cat:" in result.stdout:  # 如果是目录
                    self.current_path = new_path
                    self.path_label.setText(f'当前路径: {self.current_path}')
                    self.refresh_file_list()
                elif result.returncode == 0:  # 如果是文件
                    self.save_file(new_path, selected_item)
            except subprocess.TimeoutExpired:  # 如果超时，直接认为是文件
                self.save_file(new_path, selected_item)
        except Exception as e:
            QMessageBox.warning(self, '错误', f"无法导航到路径: {str(e)}")

    def save_file(self, remote_path, file_name):
        """保存文件到本地"""
        save_directory = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if save_directory:
            save_path = os.path.join(save_directory, file_name)
            try:
                adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')
                # 使用 adb pull 命令将文件从设备复制到本地
                subprocess.run(
                    [adb_path, '-s', self.device, 'pull', remote_path, save_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                QMessageBox.information(self, '提示', f'文件已保存到: {save_path}')
            except Exception as e:
                QMessageBox.warning(self, '错误', f"无法保存文件: {str(e)}")

    def navigate_up(self):
        """返回上一级目录"""
        if self.current_path != '/':
            self.current_path = '/'.join(self.current_path.split('/')[:-1])  # 直接使用字符串操作
            if self.current_path == '':  # 如果路径为空，设置为根目录
                self.current_path = '/'
            self.path_label.setText(f'当前路径: {self.current_path}')
            self.refresh_file_list()



class ADBTool(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.device_list = []  # 存储设备列表
        self.current_thread = None  # 用于跟踪当前执行的线程
        self.refresh_devices()  # 初始化时刷新设备列表

    def initUI(self):
        self.setStyleSheet("font-family: Microsoft YaHei;")
        self.setWindowTitle('SeaADBTools 年轻人的第一款GUI的ADB工具')
        self.setGeometry(100, 100, 800, 600)

        # 主布局
        layout = QVBoxLayout()

        # 左上角设置按钮
        self.settings_button = QPushButton('设置')
        self.settings_button.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_button)

        # 设备选择部分
        device_layout = QHBoxLayout()
        self.device_label = QLabel('选择设备:')
        self.device_combo = QComboBox()
        self.refresh_button = QPushButton('刷新设备')
        self.refresh_button.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.device_label)
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_button)
        layout.addLayout(device_layout)

        # 添加获取设备信息按钮
        self.device_info_button = QPushButton('获取设备信息')
        self.device_info_button.clicked.connect(self.get_device_info)
        layout.addWidget(self.device_info_button)

        self.ADB_label = QLabel('————ADB专区————')
        self.ADB_label.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(self.ADB_label)

        # 常用命令按钮
        command_button_layout = QHBoxLayout()
        self.reboot_button = QPushButton('重启设备')
        self.reboot_button.clicked.connect(lambda: self.execute_adb_command('reboot'))
        self.screenshot_button = QPushButton('截图')
        self.screenshot_button.clicked.connect(self.take_screenshot)
        self.install_button = QPushButton('安装APK')
        self.install_button.clicked.connect(self.install_apk)
        self.file_manager_button = QPushButton('文件管理')
        self.file_manager_button.clicked.connect(self.open_file_manager)

        command_button_layout.addWidget(self.reboot_button)
        command_button_layout.addWidget(self.screenshot_button)
        command_button_layout.addWidget(self.install_button)
        command_button_layout.addWidget(self.file_manager_button)
        layout.addLayout(command_button_layout)

        # 自定义命令输入
        self.command_input = QLineEdit(self)
        self.command_input.setPlaceholderText('输入自定义ADB命令（不需要adb开头）')
        layout.addWidget(self.command_input)

        # 执行按钮
        self.execute_button = QPushButton('执行命令')
        self.execute_button.clicked.connect(self.execute_custom_command)
        layout.addWidget(self.execute_button)

        self.FASTBOOT_label = QLabel('————FASTBOOT专区————')
        self.FASTBOOT_label.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(self.FASTBOOT_label)

        # FASTBOOT 命令按钮
        fastboot_button_layout = QHBoxLayout()
        self.fastboot_reboot_button = QPushButton('重启到FASTBOOT')
        self.fastboot_reboot_button.clicked.connect(self.reboot_to_fastboot)
        self.fastboot_flash_button = QPushButton('刷入镜像')
        self.fastboot_flash_button.clicked.connect(self.flash_image)
        self.fastboot_unlock_button = QPushButton('解锁Bootloader')
        self.fastboot_unlock_button.clicked.connect(self.unlock_bootloader)
        fastboot_button_layout.addWidget(self.fastboot_reboot_button)
        fastboot_button_layout.addWidget(self.fastboot_flash_button)
        fastboot_button_layout.addWidget(self.fastboot_unlock_button)
        layout.addLayout(fastboot_button_layout)

        # 输出显示
        self.output_display = QTextEdit(self)
        self.output_display.setReadOnly(True)
        layout.addWidget(self.output_display)

        # 添加 SeaScript 执行按钮
        self.run_script_button = QPushButton('执行 SeaScript')
        self.run_script_button.clicked.connect(self.run_sea_script)
        layout.addWidget(self.run_script_button)

        self.setLayout(layout)

    def refresh_devices(self):
        """刷新设备列表"""
        try:
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')  # 假设 adb.exe 在 adb 子目录
            result = subprocess.run(
                [adb_path, 'devices'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            )
            output = result.stdout
            devices = [line.split()[0] for line in output.splitlines() if 'device' in line and not 'offline' in line and not 'List' in line]
            self.device_list = devices
            self.device_combo.clear()
            self.device_combo.addItems(devices)
            if not devices:
                self.output_display.setText("未检测到设备，请连接设备后重试。")
        except Exception as e:
            self.output_display.setText(f"刷新设备列表时出错: {str(e)}")

    def get_selected_device(self):
        """获取当前选择的设备"""
        return self.device_combo.currentText()

    def execute_adb_command(self, command):
        """执行ADB命令"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        full_command = f"-s {device} {command}"
        self.run_command_in_thread(full_command)

    def execute_custom_command(self):
        """执行自定义命令"""
        command = self.command_input.text().strip()
        if not command:
            QMessageBox.warning(self, '错误', '请输入有效的ADB命令！')
            return

        self.run_command_in_thread(command)

    def run_command_in_thread(self, command):
        """在后台线程中运行ADB命令"""
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()  # 停止前一个线程
            self.current_thread.wait()   # 等待线程结束

        self.output_display.clear()
        self.output_display.append(f"执行命令: {command}\n")

        self.current_thread = ADBCommandThread(command)
        self.current_thread.command_output.connect(self.output_display.append)
        self.current_thread.start()

    def run_fastboot_command(self, command):
        """执行FASTBOOT命令"""
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()  # 停止前一个线程
            self.current_thread.wait()   # 等待线程结束

        self.output_display.clear()
        self.output_display.append(f"执行命令: {command}\n")

        self.current_thread = FastbootCommandThread(command)
        self.current_thread.command_output.connect(self.output_display.append)
        self.current_thread.start()

    def take_screenshot(self):
        """截图功能"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        file_path, _ = QFileDialog.getSaveFileName(self, '保存截图', '', 'PNG Files (*.png)')
        if file_path:
            try:
                adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')  # 假设 adb.exe 在 adb 子目录
                subprocess.run(f"{adb_path} -s {device} shell mkdir -p /sdcard/SeaADBTools/temp/screenshot", shell=True, check=True)
                subprocess.run(f"{adb_path} -s {device} shell screencap -p /sdcard/SeaADBTools/temp/screenshot/screenshot.png", shell=True, check=True)
                subprocess.run(f"{adb_path} -s {device} pull /sdcard/SeaADBTools/temp/screenshot/screenshot.png {file_path}", shell=True, check=True)
                QMessageBox.information(self, '提示', '截图已保存到' + file_path)
            except subprocess.CalledProcessError:
                QMessageBox.warning(self, '错误', '截图失败，请检查设备连接状态。')

    def install_apk(self):
        """安装APK功能"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        file_path, _ = QFileDialog.getOpenFileName(self, '选择APK文件', '', 'APK Files (*.apk)')
        if file_path:
            self.run_command_in_thread(f"-s {device} install {file_path}")

    def clean_sea_adb_tools_temp_files(self):
        """清理 SeaADBTools 临时文件"""
        try:
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')
            subprocess.run(f"{adb_path} shell rm -rf /sdcard/SeaADBTools/temp", shell=True, check=True)
        except subprocess.CalledProcessError:
            QMessageBox.warning(self, '错误', '清理临时文件失败，请检查设备连接状态。')

    def run_sea_script(self):
        """执行SeaScript脚本"""
        file_path, _ = QFileDialog.getOpenFileName(self, '选择SeaScript文件', '', 'SeaScript Files (*.sea)')
        if not file_path:
            return

        device = self.get_selected_device()  # 获取当前选择的设备
        sea_script = SeaScript(device)  # 将设备传递给 SeaScript
        commands = sea_script.parse_script(file_path)

        for command in commands:
            self.run_command_in_thread(command)

    def reboot_to_fastboot(self):
        """重启设备到FASTBOOT模式"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        self.run_command_in_thread(f"-s {device} reboot-bootloader")

    def flash_image(self):
        """刷入镜像文件"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        file_path, _ = QFileDialog.getOpenFileName(self, '选择镜像文件', '', 'Image Files (*.img)')
        if file_path:
            partition, ok = QInputDialog.getText(self, '选择分区', '请输入要刷入的分区（如 boot, recovery, system 等）：')
            if ok and partition:
                self.run_command_in_thread(f"-s {device} flash {partition} {file_path}")

    def unlock_bootloader(self):
        """解锁Bootloader"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        self.run_fastboot_command('oem unlock')

    def get_device_info(self):
        """获取设备信息并格式化输出"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        try:
            adb_path = os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')  # 假设 adb.exe 在 adb 子目录
            # 获取设备型号
            model = subprocess.run(
                [adb_path, '-s', device, 'shell', 'getprop', 'ro.product.model'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            ).stdout.strip()

            # 获取设备品牌
            brand = subprocess.run(
                [adb_path, '-s', device, 'shell', 'getprop', 'ro.product.brand'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            ).stdout.strip()

            # 获取设备系统版本
            version = subprocess.run(
                [adb_path, '-s', device, 'shell', 'getprop', 'ro.build.version.release'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            ).stdout.strip()

            # 获取设备序列号
            serial = subprocess.run(
                [adb_path, '-s', device, 'shell', 'getprop', 'ro.serialno'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式指定编码为 utf-8
                errors='ignore'    # 忽略无法解码的字符
            ).stdout.strip()

            # 格式化输出
            info = f"""
设备型号: {model}
设备品牌: {brand}
系统版本: Android {version}
设备序列号: {serial}
            """
            self.output_display.append(info)
        except Exception as e:
            self.output_display.append(f"获取设备信息时出错: {str(e)}")

    def open_file_manager(self):
        """打开文件管理器"""
        device = self.get_selected_device()
        if not device:
            QMessageBox.warning(self, '错误', '请先选择一个设备！')
            return

        self.file_manager_window = FileManager(device)
        self.file_manager_window.show()

    def show_settings(self):
        """显示设置窗口"""
        self.settings_window = Settings()  # 将主窗口作为父窗口传递
        self.settings_window.show()


class Settings(QWidget):
    def __init__(self):
        super().__init__()  # 不传递 parent 参数
        self.initUI()

    def initUI(self):
        self.setWindowTitle('设置')
        self.setGeometry(100, 100, 300, 200)
        layout = QVBoxLayout()

        self.theme_label = QLabel('主题:')
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['light_blue.xml', 'dark_blue.xml', 'light_red.xml', 'dark_red.xml'])
        layout.addWidget(self.theme_label)
        layout.addWidget(self.theme_combo)

        # 添加应用主题按钮
        self.apply_button = QPushButton('应用主题')
        self.apply_button.clicked.connect(self.setthemes)

        layout.addWidget(self.apply_button)

        self.setLayout(layout)

    def setthemes(self):
        """设置主题"""
        theme = self.theme_combo.currentText()
        apply_stylesheet(app, theme=theme)  # 切换主题
        # self.close()  # 应用主题后关闭设置窗口


if __name__ == '__main__':
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='light_blue.xml')  # 切换主题
    ex = ADBTool()
    ex.show()
    sys.exit(app.exec())

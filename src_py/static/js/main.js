// static/js/main.js

document.addEventListener('DOMContentLoaded', function () {
    console.log("main.js script loaded and executing."); // 调试信息

    /**
     * SweetAlert2 确认弹窗的通用主题配置
     */
    const swalWithBootstrapButtons = Swal.mixin({
        customClass: {
            // 你可以在 style.css 中为这些类定义样式，以匹配你的主题
            confirmButton: 'btn-submit', // 使用你现有的按钮样式
            cancelButton: 'btn-secondary'  // 使用你现有的次要按钮样式
        },
        buttonsStyling: false, // 必须设置成 false 来启用 customClass
        reverseButtons: true   // 反转按钮位置，“取消”在右边，“确认”在左边，更符合常规习惯
    });

    /**
     * 【重构】使用事件委托，监听所有表单的提交事件。
     * 这种方法比给每个表单都绑定一个事件更高效。
     */
    document.body.addEventListener('submit', function(event) {
        // 检查提交事件是否来自于一个带有 'delete-form' 类的表单
        const form = event.target.closest('form.delete-form');

        // 如果不是删除表单，则什么都不做，让表单正常提交
        if (!form) {
            return;
        }

        // 如果是删除表单，首先阻止它的默认提交行为
        event.preventDefault();

        // 从表单的 data-* 属性中获取自定义提示信息
        // 如果属性不存在，则使用默认的提示语
        const message = form.dataset.message || '您确定要执行此操作吗？';
        const detail = form.dataset.detail || '此操作无法撤销。';

        // 显示 SweetAlert2 弹窗
        swalWithBootstrapButtons.fire({
            title: message,
            text: detail,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '是的, 删除!',
            cancelButtonText: '取消',
        }).then((result) => {
            // .then() 会在用户与弹窗交互（点击按钮）后执行
            if (result.isConfirmed) {
                // 如果用户点击了“确定”，我们才以编程方式提交表单
                form.submit();
            }
        });
    });
});

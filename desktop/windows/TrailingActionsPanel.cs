using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Windows.Foundation;

namespace SmartSearch.Desktop;

// Content with its actions on the right while both fit; otherwise the actions move below and wrap there.
// A Grid Auto column measures wrapping actions as one line and never reserves room for a second one.
internal sealed class TrailingActionsPanel : Panel
{
    // The content keeps up to this width beside the actions before they move below it.
    private const double ContentMinimum = 240;
    private bool _stacked;

    internal double Spacing { get; init; } = 16;
    internal double StackedSpacing { get; init; } = 12;

    protected override Size MeasureOverride(Size availableSize)
    {
        var (content, actions) = (Children[0], Children[1]);
        var unbounded = new Size(double.PositiveInfinity, double.PositiveInfinity);
        content.Measure(unbounded);
        actions.Measure(unbounded);
        var actionsWidth = actions.DesiredSize.Width;
        _stacked = actionsWidth + Spacing + Math.Min(content.DesiredSize.Width, ContentMinimum) > availableSize.Width;
        if (_stacked)
        {
            var bounded = new Size(availableSize.Width, double.PositiveInfinity);
            content.Measure(bounded);
            actions.Measure(bounded);
            return new Size(Math.Max(content.DesiredSize.Width, actions.DesiredSize.Width),
                content.DesiredSize.Height + StackedSpacing + actions.DesiredSize.Height);
        }
        content.Measure(new Size(availableSize.Width - actionsWidth - Spacing, double.PositiveInfinity));
        return new Size(content.DesiredSize.Width + Spacing + actionsWidth, Math.Max(content.DesiredSize.Height, actions.DesiredSize.Height));
    }

    protected override Size ArrangeOverride(Size finalSize)
    {
        var (content, actions) = (Children[0], Children[1]);
        if (_stacked)
        {
            content.Arrange(new Rect(0, 0, finalSize.Width, content.DesiredSize.Height));
            actions.Arrange(new Rect(0, content.DesiredSize.Height + StackedSpacing, finalSize.Width, actions.DesiredSize.Height));
        }
        else
        {
            var actionsWidth = actions.DesiredSize.Width;
            content.Arrange(new Rect(0, 0, Math.Max(0, finalSize.Width - actionsWidth - Spacing), finalSize.Height));
            actions.Arrange(new Rect(finalSize.Width - actionsWidth, 0, actionsWidth, finalSize.Height));
        }
        return finalSize;
    }
}
